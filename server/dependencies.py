"""Shared server settings and client-construction helpers."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass

from alloynative import AlloyDBClient, IPType
from alloynative.capabilities import CapabilitySnapshot


def load_env_file(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""

    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_env_file()


@dataclass(frozen=True, slots=True)
class ServerSettings:
    """Environment-backed settings for the AlloyNative server runtime."""

    project_id: str
    region: str
    cluster: str
    instance: str
    database: str
    db_user: str | None = None
    ip_type: IPType = IPType.PRIVATE
    port: int = 8080
    host: str = "0.0.0.0"
    dev_mode: bool = False

    @classmethod
    def from_env(cls) -> "ServerSettings":
        """Load required runtime settings from environment variables."""

        dev_mode = os.environ.get("ALLOYNATIVE_DEV_MODE", "false").lower() == "true"
        return cls(
            project_id=os.environ.get("ALLOYNATIVE_PROJECT_ID", "local-dev-project"),
            region=os.environ.get("ALLOYNATIVE_REGION", "us-central1"),
            cluster=os.environ.get("ALLOYNATIVE_CLUSTER", "local-dev-cluster"),
            instance=os.environ.get("ALLOYNATIVE_INSTANCE", "local-dev-instance"),
            database=os.environ.get("ALLOYNATIVE_DATABASE", "local-dev-db"),
            db_user=os.environ.get("ALLOYNATIVE_DB_USER") or None,
            ip_type=IPType(os.environ.get("ALLOYNATIVE_IP_TYPE", IPType.PRIVATE.value)),
            port=int(os.environ.get("PORT", "8080")),
            host=os.environ.get("ALLOYNATIVE_HOST", "0.0.0.0"),
            dev_mode=dev_mode,
        )


class MockAlloyDBClient:
    """A lightweight in-memory client for local server boot and demos."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, object]]] = {}
        self._capabilities = CapabilitySnapshot(
            has_pgvector=True,
            has_scann=False,
            preferred_index_type="ivfflat",
        )

    @property
    def capabilities(self) -> CapabilitySnapshot:
        """Mirror the real client capability property."""

        return self._capabilities

    async def close(self) -> None:
        """Mirror the real client API."""

    async def execute(self, sql: str, params=None):
        """Return a simple echo payload for local smoke tests."""

        return [{"sql": sql, "params": dict(params or {})}]

    async def upsert_rows(
        self,
        *,
        table: str,
        rows,
        embedding_source_column: str,
        embedding_column: str = "embedding",
        id_column: str | None = None,
        embedding_model: str | None = None,
    ):
        items = self._tables.setdefault(table, [])
        returned_ids: list[str] = []

        for row in rows:
            cloned = copy.deepcopy(dict(row))
            source_text = str(cloned.get(embedding_source_column, ""))
            cloned[embedding_column] = {
                "mock_embedding_model": embedding_model or "text-embedding-005",
                "source_preview": source_text[:80],
            }

            if id_column and id_column in cloned:
                matched = False
                for index, existing in enumerate(items):
                    if existing.get(id_column) == cloned[id_column]:
                        items[index] = cloned
                        matched = True
                        break
                if not matched:
                    items.append(cloned)
                returned_ids.append(str(cloned[id_column]))
            else:
                items.append(cloned)

        return _MockUpsertResult(count=len(rows), ids=returned_ids)

    async def search_hybrid(
        self,
        *,
        table: str,
        query: str,
        filters=None,
        limit: int = 10,
        rerank: bool = False,
        text_columns=None,
        metadata_column=None,
        return_columns=None,
        id_column: str = "id",
        join_table: str | None = None,
        left_join_column: str | None = None,
        right_join_column: str | None = None,
        join_filter=None,
        **_,
    ):
        text_columns = list(text_columns or ["content"])
        rows = list(self._tables.get(table, []))
        filtered = [row for row in rows if _matches_mock_filters(row, filters or {})]

        if join_table:
            if not left_join_column or not right_join_column:
                raise ValueError(
                    "left_join_column and right_join_column are required when join_table is provided."
                )
            join_rows = list(self._tables.get(join_table, []))
            filtered = [
                row
                for row in filtered
                if any(
                    row.get(left_join_column) == join_row.get(right_join_column)
                    and _matches_mock_filters(join_row, join_filter or {})
                    for join_row in join_rows
                )
            ]

        query_terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[_MockSearchResult] = []

        for row in filtered:
            content = " ".join(str(row.get(column, "")) for column in text_columns).strip()
            haystack = content.lower()
            overlap = sum(1 for term in query_terms if term in haystack)
            score = float(overlap) / float(len(query_terms) or 1)
            payload = {}
            if metadata_column and isinstance(row.get(metadata_column), dict):
                payload.update(dict(row[metadata_column]))
            if return_columns:
                for column in return_columns:
                    payload[column] = row.get(column)
            elif not payload:
                payload = {
                    key: value
                    for key, value in row.items()
                    if key not in {"embedding"}
                }

            scored.append(
                _MockSearchResult(
                    id=str(row.get(id_column, "")),
                    content=content,
                    metadata=dict(payload),
                    payload=dict(payload),
                    score=score,
                    distance=max(0.0, 1.0 - score),
                )
            )

        scored.sort(key=lambda item: (-item.score, item.distance))
        return _MockSearchResponse(
            results=scored[:limit],
            reranked=rerank,
            candidate_count=min(len(scored), limit),
        )


@dataclass(slots=True)
class _MockUpsertResult:
    count: int
    ids: list[str]


@dataclass(slots=True)
class _MockSearchResult:
    id: str
    content: str
    metadata: dict[str, object]
    payload: dict[str, object]
    score: float
    distance: float


@dataclass(slots=True)
class _MockSearchResponse:
    results: list[_MockSearchResult]
    reranked: bool
    candidate_count: int


def _matches_mock_filters(row: dict[str, object], filters: dict[str, object]) -> bool:
    for raw_key, expected in filters.items():
        if "__" in raw_key:
            column, operator = raw_key.rsplit("__", 1)
        else:
            column, operator = raw_key, "eq"
        actual = row.get(column)

        if operator == "eq" and actual != expected:
            return False
        if operator == "ne" and actual == expected:
            return False
        if operator == "gt" and not (actual is not None and actual > expected):
            return False
        if operator == "gte" and not (actual is not None and actual >= expected):
            return False
        if operator == "lt" and not (actual is not None and actual < expected):
            return False
        if operator == "lte" and not (actual is not None and actual <= expected):
            return False
        if operator == "in" and actual not in expected:
            return False
    return True


async def build_client(settings: ServerSettings) -> AlloyDBClient:
    """Create and validate a connected AlloyNative client for the server."""

    if settings.dev_mode:
        return MockAlloyDBClient()

    return await AlloyDBClient.aconnect(
        project_id=settings.project_id,
        region=settings.region,
        cluster=settings.cluster,
        instance=settings.instance,
        database=settings.database,
        db_user=settings.db_user,
        ip_type=settings.ip_type,
    )
