import dashscope
from dotenv import load_dotenv

from config.reranker_config import reranker_config

load_dotenv()


def rerank_documents(query: str, documents: list[str]) -> list[float]:
    text_rerank_api_key = reranker_config.text_rerank_api_key  # 白炼通用key
    text_rerank_model = reranker_config.text_rerank_model

    # 调用排序模型对文档相关度打分
    response = dashscope.TextReRank.call(
        model=text_rerank_model,
        api_key=text_rerank_api_key,
        query=query,
        documents=documents,
        instruct=reranker_config.text_rerank_instruct,
        top_n=len(documents)
    )

    status_code = response.get("status_code")
    if status_code != 200:
        message = response.get("message")
        raise RuntimeError(f"DashScope rerank 调用失败: {message}")
    # 打印查看response的数据结构
    # print(response)
    rerank_scores = [0.0] * len(documents)
    results = response.get("output").get("results")
    for index, result in enumerate(results):
        rerank_scores[index] = result.get("relevance_score")

    print(f"rerank_scores:{rerank_scores}")
    return rerank_scores
