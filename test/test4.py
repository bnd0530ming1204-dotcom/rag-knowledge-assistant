import base64

from config.lm_config import lm_config
from utils.llm_utils import get_llm_client

base_str = None
with open("./data/a.png", "rb") as img:
    base_str = base64.b64encode(img.read()).decode("utf-8")


vl_ai = get_llm_client(lm_config.vl_model)

# 2 调用模型
messages = [
    {
        "role":"user",
        "content":[
                {
                    "type": "text",
                    "text": f"""这是书籍管理文件中的一张图片，图片上文部分为"这是一堆好书"，下文部分为"请好好阅读"，请用中文简要总结这张图片的内容，用于 Markdown 图片标题。"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base_str}"
                    }
                }
            ]
    }
]
response = vl_ai.invoke(messages)

print(response)

