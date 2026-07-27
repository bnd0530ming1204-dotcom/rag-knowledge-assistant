import time

from fastapi import FastAPI, BackgroundTasks

app = FastAPI()


def write_log1(email: str, content: str):
    while True:
        print(f"正在给{email}发送信息，{str}....")
        time.sleep(1)


@app.get("/send-task/{email}")
async def send_task(email: str, backgroundTasks: BackgroundTasks):
    # backgroundTasks.add_task(write_log1, email, "hello")
    # print("任务开始")
    # time.sleep(5)
    # print("任务结束")
    print("服务器运行。。。")
    return {"message": "任务执行完成"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
