"""Capability types for AlloyNative connection and index behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    """Read-only capability snapshot detected from a live AlloyDB instance."""

    has_pgvector: bool = False
    has_scann: bool = False
    preferred_index_type: str = "ivfflat"

    @classmethod
    def from_extensions(cls, extensions: set[str]) -> "CapabilitySnapshot":
        """Build a capability snapshot from installed PostgreSQL extensions."""

        has_pgvector = "vector" in extensions
        has_scann = "alloydb_scann" in extensions
        return cls(
            has_pgvector=has_pgvector,
            has_scann=has_scann,
            preferred_index_type="scann" if has_scann else "ivfflat",
        )


DEFAULT_CAPABILITIES = CapabilitySnapshot()
