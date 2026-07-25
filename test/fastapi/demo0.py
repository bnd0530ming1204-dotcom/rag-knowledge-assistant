import asyncio

from fastapi import FastAPI
from starlette.responses import StreamingResponse

app = FastAPI()


# 普通的流式方法，用了yield没用return
async def generate_stream():
    words = ["你", "好", "，", "这", "是", "流", "式", "响", "应"]
    for word in words:
        await asyncio.sleep(0.5)
        yield word.encode("utf-8")


# 流式输出接口
@app.get("/stream")
async def stream_response():
    print("流式输出web接口")
    return StreamingResponse(generate_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
