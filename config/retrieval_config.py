from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalConfig:
    initial_candidate_limit: int = 5
    rrf_candidate_limit: int = 5
    rerank_candidate_limit: int = 5
    final_output_limit: int = 5


retrieval_config = RetrievalConfig()
