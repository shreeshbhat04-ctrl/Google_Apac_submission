"""Configuration types for AlloyNative clients and connections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import AlloyNativeConfigurationError
from .version import __version__


class IPType(str, Enum):
    """Supported AlloyDB connector network modes."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    PSC = "PSC"


@dataclass(frozen=True, slots=True)
class AlloyDBConfig:
    """Immutable client configuration."""

    project_id: str
    region: str
    cluster: str
    instance: str
    database: str
    db_user: str | None = None
    ip_type: IPType = IPType.PRIVATE
    enable_iam_auth: bool = True
    refresh_strategy: str = "LAZY"
    default_embedding_model: str = "text-embedding-005"
    default_rerank_model: str = "gemini_flash_model"
    require_model_support: bool = True
    require_ai_query_engine: bool = True
    pool_size: int = 5
    max_overflow: int = 2
    user_agent: str = f"alloynative/{__version__}"

    def __post_init__(self) -> None:
        required_values = {
            "project_id": self.project_id,
            "region": self.region,
            "cluster": self.cluster,
            "instance": self.instance,
            "database": self.database,
        }
        missing = [key for key, value in required_values.items() if not value]
        if missing:
            joined = ", ".join(sorted(missing))
            raise AlloyNativeConfigurationError(
                f"Missing required AlloyDB configuration values: {joined}."
            )

        if self.pool_size < 1:
            raise AlloyNativeConfigurationError("pool_size must be at least 1.")

        if self.max_overflow < 0:
            raise AlloyNativeConfigurationError("max_overflow cannot be negative.")

    @property
    def instance_uri(self) -> str:
        """Return the canonical AlloyDB instance URI for the connector."""

        return (
            f"projects/{self.project_id}/locations/{self.region}"
            f"/clusters/{self.cluster}/instances/{self.instance}"
        )
