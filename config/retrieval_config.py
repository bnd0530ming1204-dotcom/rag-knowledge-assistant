from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class RetrievalConfig:
    initial_candidate_limit: int = 10
    rrf_candidate_limit: int = 5
    rerank_candidate_limit: int = 5
    final_output_limit: int = 5
    dense_weight: float = 0.8
    sparse_weight: float = 0.2


retrieval_config = RetrievalConfig()


def refresh_retrieval_config() -> RetrievalConfig:
    """Compatibility adapter backed by the validated application settings."""
    settings = get_settings()
    return RetrievalConfig(
        initial_candidate_limit=settings.hybrid_candidate_top_n,
        rrf_candidate_limit=settings.final_context_top_k,
        rerank_candidate_limit=settings.final_context_top_k,
        final_output_limit=settings.final_context_top_k,
        dense_weight=settings.dense_weight,
        sparse_weight=settings.sparse_weight,
    )


retrieval_config = refresh_retrieval_config()
