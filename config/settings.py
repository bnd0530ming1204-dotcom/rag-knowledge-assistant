"""Validated application settings for the production RAG path."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    dense_weight: float = Field(0.8, ge=0)
    sparse_weight: float = Field(0.2, ge=0)
    dense_top_k: int = Field(10, ge=1)
    sparse_top_k: int = Field(10, ge=1)
    hybrid_candidate_top_n: int = Field(10, ge=1)
    final_context_top_k: int = Field(5, ge=1)
    max_context_tokens: int = Field(3000, ge=128)
    query_rewrite_timeout: float = Field(8.0, gt=0)
    llm_timeout: float = Field(60.0, gt=0)
    enable_query_rewrite: bool = True
    rewrite_decision_mode: Literal["history", "conditional"] = "history"

    # Phase 2 extension points. They deliberately remain disabled in V3 Phase 1.
    enable_hyde: bool = False
    enable_rrf: bool = False
    enable_rerank: bool = False
    hyde_timeout: float = Field(15.0, gt=0)
    fusion_mode: Literal["weighted_hybrid", "explicit_rrf"] = "weighted_hybrid"
    rrf_k: int = Field(60, ge=1)
    rrf_top_n: int = Field(10, ge=1)
    rerank_top_n: int = Field(5, ge=1)
    rerank_timeout: float = Field(10.0, gt=0)
    context_selector_mode: Literal["fixed", "dynamic"] = "fixed"
    min_contexts: int = Field(1, ge=1)
    max_contexts: int = Field(5, ge=1)
    dynamic_score_gap: float = Field(0.25, ge=0)
    dynamic_min_score: float | None = None

    @model_validator(mode="after")
    def validate_retrieval(self):
        if self.dense_weight + self.sparse_weight <= 0:
            raise ValueError("dense_weight and sparse_weight cannot both be zero")
        if self.final_context_top_k > self.hybrid_candidate_top_n:
            raise ValueError("final_context_top_k cannot exceed hybrid_candidate_top_n")
        if self.min_contexts > self.max_contexts:
            raise ValueError("min_contexts cannot exceed max_contexts")
        return self


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


def reset_settings_cache() -> None:
    """Test hook for environment-based overrides."""
    get_settings.cache_clear()
