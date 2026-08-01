from pathlib import Path

import torch
from FlagEmbedding import BGEM3FlagModel

from config.embedding_config import embedding_config

_bge_m3_ef = None


def get_bge_m3_ef():
    global _bge_m3_ef
    if _bge_m3_ef is not None:
        return _bge_m3_ef

    configured_path = embedding_config.bge_m3_path
    model_source = configured_path if configured_path and Path(configured_path).exists() else embedding_config.bge_m3
    if not model_source:
        raise ValueError("请在 .env 中配置 BGE_M3_PATH 或 BGE_M3")

    configured_device = embedding_config.bge_device or "cpu"
    device = configured_device if not configured_device.startswith("cuda") or torch.cuda.is_available() else "cpu"
    use_fp16 = embedding_config.bge_fp16 and device.startswith("cuda")

    _bge_m3_ef = BGEM3FlagModel(
        model_source,
        use_fp16=use_fp16,
        device=device,
    )

    return _bge_m3_ef

# 获得向量数据，并且解析出稠密和稀疏的向浮点量值
def generate_embeddings(texts):
    """
    为文本生成向量嵌入
    :param texts: 要生成嵌入的文本列表
    :return: 包含dense和sparse向量的字典
    """
    model = get_bge_m3_ef()
    embeddings = model.encode(
        sentences=texts,
        return_dense=True,
        return_sparse=True
    )

    dense_vectors = [vector.tolist() if hasattr(vector, "tolist") else list(vector)
                     for vector in embeddings["dense_vecs"]]
    sparse_vectors = [
        {int(index): float(weight) for index, weight in vector.items()}
        for vector in embeddings["lexical_weights"]
    ]
    return {"dense": dense_vectors, "sparse": sparse_vectors}
