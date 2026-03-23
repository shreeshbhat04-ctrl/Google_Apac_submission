"""Structured result types returned by the AlloyNative client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UpsertResult:
    """Summary of an upsert_raw_text operation."""

    count: int
    ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchResult:
    """Single search result row returned by search_hybrid."""

    id: str
    content: str
    metadata: dict[str, Any]
    score: float
    payload: dict[str, Any] = field(default_factory=dict)
    distance: float | None = None


@dataclass(slots=True)
class SearchResponse:
    """Search response wrapper with rerank metadata."""

    results: list[SearchResult]
    reranked: bool = False
    candidate_count: int = 0
