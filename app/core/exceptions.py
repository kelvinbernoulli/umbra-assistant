"""Application-level exceptions, mapped to HTTP responses in main.py."""


class UmbraError(Exception):
    """Base class for all application-raised errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NamespaceIsolationError(UmbraError):
    """Raised if a request would cross a user namespace boundary. Never silence this."""

    def __init__(self, message: str = "Namespace isolation violation"):
        super().__init__(message, status_code=403)


class IngestionError(UmbraError):
    """Raised when a webhook payload fails normalization/embedding/upsert."""

    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class WebhookSignatureError(UmbraError):
    """Raised when an inbound webhook fails signature verification."""

    def __init__(self, message: str = "Invalid webhook signature"):
        super().__init__(message, status_code=401)


class VectorStoreError(UmbraError):
    def __init__(self, message: str):
        super().__init__(message, status_code=502)
