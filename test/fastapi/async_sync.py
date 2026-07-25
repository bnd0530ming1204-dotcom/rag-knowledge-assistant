import threading

from fastapi import FastAPI

app = FastAPI()

# ✅ 异步版本
@app.get("/simple-async")
async def simple_async():
    print(threading.current_thread().ident)
    return {"message": "Hello async"}

# ✅ 同步版本
# @app.get("/simple-sync")
# def simple_sync():
#     print(threading.current_thread().ident)
#     return {"message": "Hello sync"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.63.26", port=8000)