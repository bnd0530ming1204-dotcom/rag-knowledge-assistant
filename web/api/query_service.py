import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse

from processor.import_processor.main_graph import KBImportWorkflow
from processor.query_processor.main_graph import KBQueryWorkflow
from utils.mongo_history_utils import get_recent_messages, get_recent_sessions
from utils.sse_utils import create_sse_queue, sse_generator
from utils.sse_utils import push_to_session, SSEEvent
from utils.task_utils import update_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_FAILED, get_task_result
from utils.retrieval_errors import RetrievalError
from utils.retrieval_errors import ApplicationError
from utils.retrieval_errors import DocumentParseFailed, GenerationFailed, GenerationTimeout
from config.settings import get_settings
from utils.observability import create_trace, finish_trace, get_trace

app = FastAPI()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))


class QueryRequest(BaseModel):
    query: str
    session_id: str
    is_stream: bool = False


@app.get("/chat.html")
async def chat():
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    chat_html_path = current_dir_parent_path / "page" / "chat.html"
    return FileResponse(chat_html_path)


@app.post("/chat")
@app.post("/query", deprecated=True)
async def query(backgroundTasks: BackgroundTasks, query: QueryRequest):
    user_query = query.query
    session_id = query.session_id
    is_stream = query.is_stream
    request_id = uuid.uuid4().hex
    settings = get_settings()
    create_trace(request_id, session_id, user_query, settings.dense_weight, settings.sparse_weight)

    if is_stream:
        create_sse_queue(request_id)

    update_task_status(request_id, TASK_STATUS_PROCESSING, is_stream)

    if is_stream:
        backgroundTasks.add_task(run_query_graph, request_id, session_id, user_query, is_stream)
        return {"message": "任务已经开始，请耐心等待", "session_id": session_id, "request_id": request_id}
    else:
        try:
            result = run_query_graph(request_id, session_id, user_query, is_stream)
        except (RetrievalError, ApplicationError) as exc:
            raise HTTPException(status_code=503, detail={"code": exc.code, "message": "RAG service is temporarily unavailable"}) from exc
        answer = get_task_result(request_id, "answer", "")
        return {
            "message": "处理完成",
            "session_id": session_id,
            "request_id": request_id,
            "answer": answer,
            "sources": result.get("sources", []) if isinstance(result, dict) else [],
            "image_urls": result.get("image_urls", []) if isinstance(result, dict) else [],
            "context_count": result.get("context_count", 0) if isinstance(result, dict) else 0,
            "context_token_count": result.get("context_token_count", 0) if isinstance(result, dict) else 0,
        }


@app.post("/upload")
def upload_pdf(file: UploadFile = File(...)):
    original_name = Path(file.filename or "").name
    if not original_name or Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持上传 PDF 文件")

    task_id = uuid.uuid4().hex
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    saved_path = task_dir / original_name

    try:
        with saved_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        final_state = KBImportWorkflow().run(
            {"task_id": task_id, "import_file_path": str(saved_path)},
            stream=False,
        )
        chunks = final_state.get("chunks") or []
        return {
            "status": "completed",
            "task_id": task_id,
            "file_name": original_name,
            "saved_path": str(saved_path),
            "markdown_path": final_state.get("md_path", ""),
            "chunks_count": len(chunks),
        }
    except HTTPException:
        raise
    except Exception as exc:
        error = DocumentParseFailed("document parsing failed")
        raise HTTPException(status_code=500, detail={"code": error.code, "message": "PDF processing failed"}) from exc
    finally:
        file.file.close()


def run_query_graph(request_id: str, session_id: str, user_query: str, is_stream: bool):
    print("调用搜索工作流")

    init_state = {
        "original_query": user_query,
        "session_id": session_id,
        "request_id": request_id,
        "is_stream": is_stream
    }

    try:
        workflow = KBQueryWorkflow()
        result = workflow.run(init_state, stream=is_stream)
        if is_stream:
            for _ in result:
                pass
        return result
    except (RetrievalError, ApplicationError) as exc:
        update_task_status(request_id, TASK_STATUS_FAILED, is_stream)
        current_trace = get_trace(request_id)
        if not current_trace or current_trace.terminal_status != "CANCELLED":
            finish_trace(request_id, "TIMEOUT" if exc.code == "GENERATION_TIMEOUT" else "FAILED", exc.code)
        if is_stream:
            # Generation errors are already emitted by the answer node.
            if not isinstance(exc, (GenerationFailed, GenerationTimeout)):
                push_to_session(request_id, SSEEvent.ERROR, {
                "code": exc.code,
                "message": "RAG service is temporarily unavailable",
                })
                push_to_session(request_id, SSEEvent.CLOSE, {})
        raise
    except Exception as exc:
        update_task_status(request_id, TASK_STATUS_FAILED, is_stream)
        finish_trace(request_id, "FAILED", "QUERY_PROCESSING_FAILED")
        if is_stream:
            push_to_session(request_id, SSEEvent.ERROR, {
                "code": "QUERY_PROCESSING_FAILED",
                "message": "Query processing failed",
            })
            push_to_session(request_id, SSEEvent.CLOSE, {})
        raise


@app.get("/stream/{session_id}")
async def stream(session_id: str, request: Request):
    print("追踪生成结果...")
    return StreamingResponse(
        sse_generator(session_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/history/{session_id}")
async def history(session_id: str, limit: int = 50):
    records = get_recent_messages(session_id, limit=limit)
    items = []
    for r in records:
        items.append({
            "_id": str(r.get("_id")) if r.get("_id") is not None else "",
            "session_id": r.get("session_id", ""),
            "role": r.get("role", ""),
            "text": r.get("text", ""),
            "rewritten_query": r.get("rewritten_query", ""),
            "item_names": r.get("item_names", []),
            "image_urls": r.get("image_urls", []),
            "sources": r.get("sources", []),
            "ts": r.get("ts")
        })
    return {"session_id": session_id, "items": items}


@app.get("/history")
async def history_sessions(limit: int = 50):
    sessions = get_recent_sessions(limit=limit)
    return {"items": [{
        "session_id": r.get("_id", ""),
        "updated_at": r.get("updated_at"),
        "preview": r.get("preview", ""),
        "message_count": r.get("message_count", 0),
    } for r in sessions]}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
