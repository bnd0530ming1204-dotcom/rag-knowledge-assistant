import os
import subprocess

# 使用本地mineru
env = os.environ.copy()
env["MINERU_MODEL_SOURCE"] = "local"

# cmd
cmd = "mineru -p ./data/example.pdf -o ./output --backend pipeline"

# 子进程
proc = subprocess.Popen(
    args = cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    errors="replace",  # 遇到乱码时替换
    text=True,  # 输出的内容是字符串 不是字节
    encoding="utf-8",  # 用指定的中文字符集进行编解码
    bufsize=1  # 按行缓冲，只要缓冲区一行满了就输出
)

# 获取日志信息
for line in proc.stdout:
    print(f"执行MinerU产生的日志：{line}")

wait_code = proc.wait()

if wait_code ==0:
    print("成功！")
