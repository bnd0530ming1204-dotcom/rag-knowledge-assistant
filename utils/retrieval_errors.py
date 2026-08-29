"""Stable, sanitized retrieval failure types for API and SSE boundaries."""

class RetrievalError(RuntimeError):
    code = "RETRIEVAL_FAILED"

class EmbeddingUnavailable(RetrievalError):
    code = "EMBEDDING_UNAVAILABLE"

class VectorDatabaseUnavailable(RetrievalError):
    code = "VECTOR_DATABASE_UNAVAILABLE"

class RetrievalFailed(RetrievalError):
    code = "RETRIEVAL_FAILED"
