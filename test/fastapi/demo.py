from fastapi import FastAPI

"""
pip install fastapi
pip install "uvicorn[standard]"
用uvicorn服务插件启动你的app(后端程序)
uv uvicorn run demo:app
"""
app = FastAPI()

@app.get("/read_root")
def read_root():
    print("read_root后端接口被访问...")
    print("read_root后端接口被访问...")
    print("read_root后端接口被访问...")
    return {"hello":"world"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.63.38", port=8001)