"""Errors raised while validating, extracting, indexing, and querying documents."""


class DocumentError(Exception):
    """Base error with a user-safe explanation."""


class DocumentValidationError(DocumentError):
    """A source file is unsupported, too large, unreadable, or unsafe."""


class DocumentExtractionError(DocumentError):
    """A supported file could not yield traceable text."""


class ProviderUnavailableError(DocumentError):
    """A configured local model provider is unavailable or incompatible."""


DocumentProviderError = ProviderUnavailableError


class IndexIntegrityError(DocumentError):
    """Persisted index data is missing, corrupt, or incompatible."""


class QueryCancelledError(DocumentError):
    """A document operation was cancelled by the user."""
