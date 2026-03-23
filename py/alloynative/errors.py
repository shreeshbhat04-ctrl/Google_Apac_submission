"""Error types for the AlloyNative SDK."""


class AlloyNativeError(Exception):
    """Base exception for all AlloyNative failures."""


class AlloyNativeConfigurationError(AlloyNativeError):
    """Raised when client configuration is invalid or incomplete."""


class AlloyNativeAuthError(AlloyNativeError):
    """Raised when IAM principal discovery or authentication fails."""


class AlloyNativeConnectionError(AlloyNativeError):
    """Raised when the SDK cannot connect to AlloyDB."""


class AlloyNativeValidationError(AlloyNativeError):
    """Raised when startup validation finds an unsupported environment."""


class AlloyNativeExtensionError(AlloyNativeValidationError):
    """Raised when a required PostgreSQL extension is missing or outdated."""


class AlloyNativeModelError(AlloyNativeValidationError):
    """Raised when a required model is unavailable or unusable."""


class AlloyNativeIndexError(AlloyNativeValidationError):
    """Raised when vector index expectations are not met."""


class AlloyNativeQueryError(AlloyNativeError):
    """Raised when SQL generation inputs are invalid."""
