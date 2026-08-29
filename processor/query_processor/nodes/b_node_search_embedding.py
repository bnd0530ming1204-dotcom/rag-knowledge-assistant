import json

from config.milvus_config import milvus_config
from config.retrieval_config import retrieval_config
from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client, create_hybrid_search_requests, hybrid_search
from utils.retrieval_errors import EmbeddingUnavailable, RetrievalFailed, VectorDatabaseUnavailable


class NodeSearchEmbedding(NodeBase):
    """
   节点功能：基于已确认主体名+改写后的用户问题，执行Milvus向量数据库混合检索
   """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_search_embedding"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        # TODO

        # 1 参数处理
        logger.info(f"【{self.name}】节点逻辑")
        query = state.get("rewritten_query")  # 语义搜索条件

        try:
            query_embeddings = generate_embeddings([query])
        except Exception as exc:
            raise EmbeddingUnavailable("Query embedding is unavailable") from exc
        dense_vector = query_embeddings["dense"][0]
        sparse_vector = query_embeddings["sparse"][0]

        # 2 milvus客户端
        try:
            milvus_client = get_milvus_client()
            milvus_client.load_collection(milvus_config.chunks_collection)
        except Exception as exc:
            raise VectorDatabaseUnavailable("Vector database is unavailable") from exc
        chunks_collection = milvus_config.chunks_collection  # 表(集合)

        # 3 请求对象
        reqs = create_hybrid_search_requests(
            dense_vector=dense_vector,
            sparse_vector=sparse_vector,
            expr=None,
            limit=retrieval_config.initial_candidate_limit,
        )

        # 4 发送请求
        response = hybrid_search(
            client=milvus_client,
            collection_name=chunks_collection,
            reqs=reqs,
            ranker_weights=(retrieval_config.dense_weight, retrieval_config.sparse_weight),
            limit=retrieval_config.initial_candidate_limit,
            output_fields=["chunk_id", "content", "title", "file_title"]
        )

        if response is None:
            raise RetrievalFailed("Hybrid retrieval returned an invalid response")
        hits = response[0] if response else []
        final_docs = []
        for hit in hits[:retrieval_config.final_output_limit]:
            entity = hit.get("entity") if isinstance(hit, dict) else getattr(hit, "entity", None)
            entity = dict(entity or {})
            score = hit.get("distance") if isinstance(hit, dict) else getattr(hit, "distance", None)
            entity.update({"score": float(score) if score is not None else None, "source": "local", "url": None})
            final_docs.append(entity)
        return {"embedding_chunks": hits, "reranked_docs": final_docs}


if __name__ == "__main__":
    node_search_embedding = NodeSearchEmbedding()
    init_state = {
        "item_names": ["兄弟HAK180烫金机", "百度一下"],
        "rewritten_query": "兄弟请帮我查一下HAK180烫金机是什么?"
    }
    process = node_search_embedding.process(init_state)
    print(json.dumps(process, ensure_ascii=False, indent=4))
