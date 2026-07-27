import asyncio
from itertools import count

from fastapi import FastAPI, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有的源
    allow_credentials=True,  # 允许客户端传递cookie
    allow_methods=["*"],  # get和post都行
    allow_headers=["*"],  # 请求头所有信息都行
)

task_queues = {}


@app.get("/query/{session_id}")
async def query_by_session(session_id: str, backgroundTasks: BackgroundTasks):
    backgroundTasks.add_task(long_task, session_id)
    return {"message": "任务已经开始，请耐心等待", "session_id": session_id}

# 调用工作流的长耗时方法
async def long_task(session_id: str):
    print("开始执行长耗时方法.....")
    queue = asyncio.Queue()
    task_queues[session_id] = queue

    for i in range(10):
        await asyncio.sleep(1)
        msg = f"这是工作流的第{i}条执行结果\n\n"
        await queue.put(msg)

    await queue.put(None)


@app.get("/stream/{session_id}")
async def stream_by_session(session_id: str):
    print("我来问问，出答案了没？")
    return StreamingResponse(
        event_generator(session_id),
        media_type="text/event-stream"
    )

# 封装sse输出结果
async def event_generator(session_id: str):
    while session_id not in task_queues:
        await asyncio.sleep(0.1)
    queue = task_queues[session_id]

    while True:
        msg = await queue.get()
        if msg is None:
            break
        yield f"data: {msg}\n\n"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)

