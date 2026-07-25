import asyncio
import time


async def download_file(name):
    print(f"开始{name}下载文件")
    await asyncio.sleep(2)
    print(f"下载{name}完成")


async def main():
    await asyncio.gather(
        download_file("文件1"),
        download_file("文件2"),
        download_file("文件3")
    )
time_begin = time.time()
asyncio.run(main())
time_end = time.time()

print(f"下载总耗时{time_end - time_begin}")
