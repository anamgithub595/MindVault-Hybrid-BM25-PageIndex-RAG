"""
app/core/exceptions.py
───────────────────────
All domain-specific exceptions. Raised by service layers,
mapped to HTTP responses in route handlers or the global handler.
"""


class MindVaultError(Exception):
    """Base for all MindVault errors."""


# ── Ingestion ─────────────────────────────────────────────────────────────
class UnsupportedFileTypeError(MindVaultError):
    def __init__(self, ext: str):
        super().__init__(f"Unsupported file type: '{ext}'")
        self.extension = ext


class FileTooLargeError(MindVaultError):
    def __init__(self, size: int, max_bytes: int):
        super().__init__(
            f"File {size/1_048_576:.1f} MB exceeds limit of {max_bytes/1_048_576:.0f} MB"
        )


class ParseError(MindVaultError):
    """Raised when a connector fails to parse a document."""


# ── PageIndex ─────────────────────────────────────────────────────────────
class PageIndexSubmitError(MindVaultError):
    """Failed to submit document to PageIndex API."""


class PageIndexTimeoutError(MindVaultError):
    """PageIndex processing/retrieval timed out."""


class PageIndexRetrievalError(MindVaultError):
    """PageIndex retrieval task failed."""


# ── Retrieval ─────────────────────────────────────────────────────────────
class EmptyQueryError(MindVaultError):
    """Query is empty after normalisation."""


class NoResultsError(MindVaultError):
    """No pages matched the query in either BM25 or PageIndex."""


# ── Generation ────────────────────────────────────────────────────────────
class LLMProviderError(MindVaultError):
    """Upstream LLM API error."""


# ── Database ──────────────────────────────────────────────────────────────
class DocumentNotFoundError(MindVaultError):
    def __init__(self, doc_id: int):
        super().__init__(f"Document {doc_id} not found")
        self.doc_id = doc_id
