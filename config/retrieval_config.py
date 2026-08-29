from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalConfig:
    initial_candidate_limit: int = 10
    rrf_candidate_limit: int = 5
    rerank_candidate_limit: int = 5
    final_output_limit: int = 5
    dense_weight: float = 0.8
    sparse_weight: float = 0.2


retrieval_config = RetrievalConfig()
