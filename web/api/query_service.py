import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from starlette.responses import FileResponse, StreamingResponse

from processor.import_processor.main_graph import KBImportWorkflow
from processor.query_processor.main_graph import KBQueryWorkflow
from utils.mongo_history_utils import get_recent_messages
from utils.sse_utils import create_sse_queue, sse_generator
from utils.task_utils import update_task_status, TASK_STATUS_PROCESSING, get_task_result

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

    if is_stream:
        create_sse_queue(session_id)

    update_task_status(session_id, TASK_STATUS_PROCESSING, is_stream)  # 记录进度

    if is_stream:
        backgroundTasks.add_task(run_query_graph, session_id, user_query, is_stream)  # run_query_graph调用工作流
        return {"message": "任务已经开始，请耐心等待", "session_id": session_id}
    else:
        run_query_graph(session_id, user_query, is_stream)
        answer = get_task_result(session_id, "answer", "")
        return {
            "message": "处理完成",
            "session_id": session_id,
            "answer": answer
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
        raise HTTPException(status_code=500, detail=f"PDF 处理失败: {exc}") from exc
    finally:
        file.file.close()


def run_query_graph(session_id: str, user_query: str, is_stream: bool):
    print("调用搜索工作流")

    init_state = {
        "original_query": user_query,
        "session_id": session_id,
        "is_stream": is_stream
    }

    workflow = KBQueryWorkflow()
    result = workflow.run(init_state, stream=is_stream)
    if is_stream:
        for _ in result:
            pass
    return result


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
            "ts": r.get("ts")
        })
    return {"session_id": session_id, "items": items}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
