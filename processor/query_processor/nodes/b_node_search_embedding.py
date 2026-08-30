import json
import queue
import threading
import time

from config.milvus_config import milvus_config
from config.retrieval_config import retrieval_config
from config.settings import get_settings
from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client, create_hybrid_search_requests, hybrid_search
from utils.retrieval_errors import EmbeddingUnavailable, RetrievalFailed, VectorDatabaseUnavailable
from utils.metadata_utils import normalize_chunk_metadata
from utils.observability import add_fallback, update_trace
from utils.fusion import reciprocal_rank_fusion
from utils.llm_utils import get_llm_client
from utils.rerank_stage import optional_rerank
from utils.retrieval_strategy import HYDE_HYBRID, route_strategy
from processor.query_processor.prompt.search_embedding_hyde import HYDE_PROMPT


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
        query = state.get("rewritten_query") or state.get("original_query", "")
        settings = get_settings()
        strategy = route_strategy(query, settings.enable_hyde)
        retrieval_query = query
        hyde_used = strategy.strategy == HYDE_HYBRID
        hyde_latency_ms = 0.0
        hyde_fallback = False
        if hyde_used:
            started = time.perf_counter()
            try:
                retrieval_query = query + " " + self._generate_hyde(query, settings.hyde_timeout)
            except Exception:
                retrieval_query = query
                hyde_used = False
                hyde_fallback = True
                strategy = route_strategy(query, False)
            hyde_latency_ms = round((time.perf_counter() - started) * 1000, 3)

        request_id = state.get("request_id", state.get("session_id", ""))
        embed_started = time.perf_counter()
        try:
            query_embeddings = generate_embeddings([retrieval_query])
        except Exception as exc:
            raise EmbeddingUnavailable("Query embedding is unavailable") from exc
        embedding_latency_ms = round((time.perf_counter() - embed_started) * 1000, 3)
        dense_vector = query_embeddings["dense"][0]
        sparse_vector = query_embeddings["sparse"][0]

        # 2 milvus客户端
        try:
            milvus_client = get_milvus_client()
            milvus_client.load_collection(milvus_config.chunks_collection)
        except Exception as exc:
            raise VectorDatabaseUnavailable("Vector database is unavailable") from exc
        chunks_collection = milvus_config.chunks_collection  # 表(集合)

        retrieval_started = time.perf_counter()
        output_fields = ["chunk_id", "content", "title", "file_title", "parent_title", "locators"]
        explicit_rrf = settings.enable_rrf and settings.fusion_mode == "explicit_rrf"
        dense_hits, sparse_hits = [], []
        if explicit_rrf:
            try:
                dense_raw = milvus_client.search(
                    collection_name=chunks_collection, data=[dense_vector], anns_field="dense_vector",
                    limit=settings.dense_top_k, search_params={"metric_type": "COSINE"}, output_fields=output_fields)
                sparse_raw = milvus_client.search(
                    collection_name=chunks_collection, data=[sparse_vector], anns_field="sparse_vector",
                    limit=settings.sparse_top_k, search_params={"metric_type": "IP"}, output_fields=output_fields)
                dense_hits = dense_raw[0] if dense_raw else []
                sparse_hits = sparse_raw[0] if sparse_raw else []
                candidates = reciprocal_rank_fusion(dense_hits, sparse_hits, settings.rrf_k, settings.rrf_top_n)
                hits = candidates
            except Exception:
                explicit_rrf = False
                add_fallback(request_id, "explicit_rrf_failure_weighted_hybrid")
                hits, candidates = self._weighted_hybrid(
                    milvus_client, chunks_collection, dense_vector, sparse_vector, output_fields, settings)
        else:
            hits, candidates = self._weighted_hybrid(
                milvus_client, chunks_collection, dense_vector, sparse_vector, output_fields, settings)
        retrieval_latency_ms = round((time.perf_counter() - retrieval_started) * 1000, 3)

        rerank = optional_rerank(query, candidates, settings.enable_rerank,
                                 settings.rerank_top_n, settings.rerank_timeout)
        final_docs = rerank.documents[:settings.final_context_top_k] if settings.context_selector_mode == "fixed" else rerank.documents
        update_trace(request_id, embedding_latency_ms=embedding_latency_ms,
                     retrieval_latency_ms=retrieval_latency_ms, candidate_count=len(candidates),
                     retrieval_strategy=strategy.strategy, hyde_used=hyde_used,
                     hyde_latency_ms=hyde_latency_ms, hyde_fallback=hyde_fallback,
                     fusion_mode="explicit_rrf" if explicit_rrf else "weighted_hybrid",
                     dense_count=len(dense_hits), sparse_count=len(sparse_hits),
                     rrf_candidate_count=len(candidates) if explicit_rrf else 0,
                     rerank_used=rerank.used, rerank_latency_ms=rerank.latency_ms,
                     rerank_scores=rerank.scores, rerank_fallback=rerank.fallback)
        return {"embedding_chunks": hits, "reranked_docs": final_docs}

    @staticmethod
    def _normalize_hit(hit):
        entity = hit.get("entity") if isinstance(hit, dict) else getattr(hit, "entity", None)
        entity = dict(entity or {})
        score = hit.get("distance") if isinstance(hit, dict) else getattr(hit, "distance", None)
        entity.update({"score": float(score) if score is not None else None, "source": "local", "url": None})
        return normalize_chunk_metadata(entity)

    @classmethod
    def _weighted_hybrid(cls, client, collection, dense_vector, sparse_vector, output_fields, settings):
        reqs = create_hybrid_search_requests(
            dense_vector=dense_vector, sparse_vector=sparse_vector, expr=None,
            limit=settings.hybrid_candidate_top_n, dense_limit=settings.dense_top_k,
            sparse_limit=settings.sparse_top_k)
        response = hybrid_search(
            client=client, collection_name=collection, reqs=reqs,
            ranker_weights=(settings.dense_weight, settings.sparse_weight),
            limit=settings.hybrid_candidate_top_n, output_fields=output_fields)
        if response is None:
            raise RetrievalFailed("Hybrid retrieval returned an invalid response")
        hits = response[0] if response else []
        return hits, [cls._normalize_hit(hit) for hit in hits]

    @staticmethod
    def _generate_hyde(query: str, timeout: float) -> str:
        output = queue.Queue()
        def invoke():
            try:
                output.put(("ok", get_llm_client().invoke(HYDE_PROMPT.format(rewritten_query=query)).content))
            except Exception as exc:
                output.put(("error", exc))
        threading.Thread(target=invoke, daemon=True).start()
        try:
            kind, value = output.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("HyDE timed out") from exc
        if kind == "error" or not str(value).strip():
            raise RuntimeError("HyDE failed")
        return str(value).strip()


if __name__ == "__main__":
    node_search_embedding = NodeSearchEmbedding()
    init_state = {
        "item_names": ["兄弟HAK180烫金机", "百度一下"],
        "rewritten_query": "兄弟请帮我查一下HAK180烫金机是什么?"
    }
    process = node_search_embedding.process(init_state)
    print(json.dumps(process, ensure_ascii=False, indent=4))
