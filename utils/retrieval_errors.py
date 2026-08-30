"""Stable, sanitized retrieval failure types for API and SSE boundaries."""

class RetrievalError(RuntimeError):
    code = "RETRIEVAL_FAILED"
    recoverable = False

class EmbeddingUnavailable(RetrievalError):
    code = "EMBEDDING_UNAVAILABLE"

class VectorDatabaseUnavailable(RetrievalError):
    code = "VECTOR_DATABASE_UNAVAILABLE"

class RetrievalFailed(RetrievalError):
    code = "RETRIEVAL_FAILED"


class ApplicationError(RuntimeError):
    code = "APPLICATION_FAILED"
    recoverable = False


class QueryRewriteFailed(ApplicationError):
    code = "QUERY_REWRITE_FAILED"
    recoverable = True


class HistoryUnavailable(ApplicationError):
    code = "HISTORY_UNAVAILABLE"
    recoverable = True


class GenerationTimeout(ApplicationError):
    code = "GENERATION_TIMEOUT"


class GenerationFailed(ApplicationError):
    code = "GENERATION_FAILED"


class DocumentParseFailed(ApplicationError):
    code = "DOCUMENT_PARSE_FAILED"
