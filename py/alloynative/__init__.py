"""Public package exports for AlloyNative."""

from .capabilities import CapabilitySnapshot
from .client import AlloyDBClient
from .config import AlloyDBConfig, IPType
from .errors import (
    AlloyNativeAuthError,
    AlloyNativeConfigurationError,
    AlloyNativeConnectionError,
    AlloyNativeError,
    AlloyNativeExtensionError,
    AlloyNativeIndexError,
    AlloyNativeModelError,
    AlloyNativeQueryError,
    AlloyNativeValidationError,
)
from .results import SearchResponse, SearchResult, UpsertResult
from .index import AlloyIndex
from .version import __version__

__all__ = [
    "AlloyDBClient",
    "AlloyIndex",
    "AlloyDBConfig",
    "CapabilitySnapshot",
    "IPType",
    "AlloyNativeError",
    "AlloyNativeConfigurationError",
    "AlloyNativeAuthError",
    "AlloyNativeConnectionError",
    "AlloyNativeValidationError",
    "AlloyNativeExtensionError",
    "AlloyNativeModelError",
    "AlloyNativeIndexError",
    "AlloyNativeQueryError",
    "SearchResult",
    "SearchResponse",
    "UpsertResult",
    "__version__",
]
