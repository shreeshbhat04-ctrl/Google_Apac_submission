"""Public AlloyNative client for AlloyDB connection, storage, and retrieval."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .capabilities import CapabilitySnapshot, DEFAULT_CAPABILITIES
from .config import AlloyDBConfig, IPType
from .connection import AlloyDBConnectionManager
from .results import SearchResponse, SearchResult, UpsertResult
from .sql import (
    build_search_hybrid_statement,
    build_upsert_raw_text_statement,
    build_upsert_rows_statement,
)
from .sync import SyncRunner
from .validation import ValidationReport, validate_environment


class AlloyDBClient:
    """High-level AlloyNative client backed by an async AlloyDB connection manager."""

    def __init__(
        self,
        config: AlloyDBConfig,
        *,
        connection_manager: AlloyDBConnectionManager | None = None,
        validator=validate_environment,
    ) -> None:
        self.config = config
        self._connection_manager = connection_manager or AlloyDBConnectionManager(config)
        self._validator = validator
        self._validation_report: ValidationReport | None = None

    @property
    def validation_report(self) -> ValidationReport | None:
        """Expose the last successful validation report."""

        return self._validation_report

    @property
    def capabilities(self) -> CapabilitySnapshot:
        """Expose runtime-detected index/vector capabilities."""

        capabilities = getattr(self._connection_manager, "capabilities", DEFAULT_CAPABILITIES)
        return capabilities if isinstance(capabilities, CapabilitySnapshot) else DEFAULT_CAPABILITIES

    @classmethod
    async def aconnect(
        cls,
        *,
        project_id: str,
        region: str,
        cluster: str,
        instance: str,
        database: str,
        db_user: str | None = None,
        ip_type: IPType = IPType.PRIVATE,
        connection_manager: AlloyDBConnectionManager | None = None,
        validator=validate_environment,
        **config_overrides: Any,
    ) -> "AlloyDBClient":
        """Create, connect, and validate an async AlloyNative client."""

        config = AlloyDBConfig(
            project_id=project_id,
            region=region,
            cluster=cluster,
            instance=instance,
            database=database,
            db_user=db_user,
            ip_type=ip_type,
            **config_overrides,
        )
        client = cls(
            config,
            connection_manager=connection_manager,
            validator=validator,
        )
        await client._connection_manager.connect()
        client._validation_report = await validator(client._connection_manager, config)
        return client

    @classmethod
    def connect(cls, **kwargs: Any) -> "AlloyDBClient":
        """Sync wrapper around aconnect() for non-async callers."""

        return SyncRunner.run(cls.aconnect(**kwargs))

    async def close(self) -> None:
        """Close the underlying engine and connector."""

        await self._connection_manager.close()

    async def execute(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute arbitrary SQL as an escape hatch."""

        return await self._connection_manager.execute(sql, params)

    async def upsert_raw_text(
        self,
        *,
        table: str,
        texts: Sequence[str],
        metadata: Sequence[Mapping[str, Any]] | None = None,
        embedding_model: str | None = None,
        content_column: str = "content",
        metadata_column: str = "metadata",
        embedding_column: str = "embedding",
        id_column: str | None = None,
        ids: Sequence[str] | None = None,
    ) -> UpsertResult:
        """Insert or upsert raw text while generating embeddings inside AlloyDB."""

        statement = build_upsert_raw_text_statement(
            table=table,
            texts=texts,
            metadata=metadata,
            embedding_model=embedding_model or self.config.default_embedding_model,
            content_column=content_column,
            metadata_column=metadata_column,
            embedding_column=embedding_column,
            id_column=id_column,
            ids=ids,
        )
        rows = await self._connection_manager.fetch_all(statement.sql, statement.params)
        returned_ids = [str(row["id"]) for row in rows if "id" in row]
        return UpsertResult(count=len(texts), ids=returned_ids)

    async def upsert_rows(
        self,
        *,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        embedding_source_column: str,
        embedding_model: str | None = None,
        embedding_column: str = "embedding",
        id_column: str | None = None,
    ) -> UpsertResult:
        """Insert or upsert arbitrary rows while generating embeddings from one column."""

        statement = build_upsert_rows_statement(
            table=table,
            rows=rows,
            embedding_source_column=embedding_source_column,
            embedding_model=embedding_model or self.config.default_embedding_model,
            embedding_column=embedding_column,
            id_column=id_column,
        )
        result_rows = await self._connection_manager.fetch_all(statement.sql, statement.params)
        returned_ids = [str(row["id"]) for row in result_rows if "id" in row]
        return UpsertResult(count=len(rows), ids=returned_ids)

    async def search_hybrid(
        self,
        *,
        table: str,
        query: str,
        filters: Mapping[str, Any] | None = None,
        limit: int = 10,
        embedding_model: str | None = None,
        rerank: bool = False,
        rerank_model: str | None = None,
        id_column: str = "id",
        text_columns: Sequence[str] | None = None,
        metadata_column: str | None = "metadata",
        return_columns: Sequence[str] | None = None,
        embedding_column: str = "embedding",
        candidate_limit: int | None = None,
        join_table: str | None = None,
        left_join_column: str | None = None,
        right_join_column: str | None = None,
        join_filter: Mapping[str, Any] | None = None,
    ) -> SearchResponse:
        """Run hybrid search with optional LLM reranking."""

        statement = build_search_hybrid_statement(
            table=table,
            query=query,
            filters=filters,
            limit=limit,
            embedding_model=embedding_model or self.config.default_embedding_model,
            rerank=rerank,
            rerank_model=rerank_model or self.config.default_rerank_model,
            id_column=id_column,
            text_columns=text_columns,
            metadata_column=metadata_column,
            return_columns=return_columns,
            embedding_column=embedding_column,
            candidate_limit=candidate_limit,
            join_table=join_table,
            left_join_column=left_join_column,
            right_join_column=right_join_column,
            join_filter=join_filter,
        )
        rows = await self._connection_manager.fetch_all(statement.sql, statement.params)
        results = [self._search_result_from_row(row) for row in rows]
        return SearchResponse(
            results=results,
            reranked=rerank,
            candidate_count=len(rows),
        )

    @staticmethod
    def _search_result_from_row(row: Mapping[str, Any]) -> SearchResult:
        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"raw": payload}
        if payload is None:
            payload = {}
        metadata = dict(payload)

        score_value = row.get("score")
        distance_value = row.get("distance")
        return SearchResult(
            id=str(row.get("id", "")),
            content=str(row.get("content", "")),
            metadata=metadata,
            score=float(score_value if score_value is not None else 0.0),
            payload=dict(payload),
            distance=float(distance_value) if distance_value is not None else None,
        )
