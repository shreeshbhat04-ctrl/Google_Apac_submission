"""Pinecone-familiar index wrapper built on top of AlloyDBClient."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .capabilities import CapabilitySnapshot
from .client import AlloyDBClient
from .errors import AlloyNativeQueryError
from .results import SearchResponse, UpsertResult
from .sync import SyncRunner


class AlloyIndex:
    """Friendly table-bound wrapper around AlloyDBClient for search workloads."""

    def __init__(
        self,
        *,
        client: AlloyDBClient,
        table: str,
        id_column: str = "id",
        text_columns: Sequence[str] | None = None,
        metadata_column: str | None = "metadata",
        embedding_column: str = "embedding",
        embedding_model: str | None = None,
        embedding_source_column: str | None = None,
    ) -> None:
        self._client = client
        self.table = table
        self.id_column = id_column
        self.text_columns = list(text_columns or ["content"])
        self.metadata_column = metadata_column
        self.embedding_column = embedding_column
        self.embedding_model = embedding_model
        self.embedding_source_column = embedding_source_column

    @property
    def client(self) -> AlloyDBClient:
        """Expose the underlying lower-level client."""

        return self._client

    @property
    def capabilities(self) -> CapabilitySnapshot:
        """Expose detected live-instance capabilities."""

        return self._client.capabilities

    @classmethod
    async def aconnect(
        cls,
        *,
        table: str,
        id_column: str = "id",
        text_columns: Sequence[str] | None = None,
        metadata_column: str | None = "metadata",
        embedding_column: str = "embedding",
        embedding_model: str | None = None,
        embedding_source_column: str | None = None,
        **client_kwargs: Any,
    ) -> "AlloyIndex":
        """Create a connected client and wrap it in a table-bound AlloyIndex."""

        client = await AlloyDBClient.aconnect(**client_kwargs)
        return cls(
            client=client,
            table=table,
            id_column=id_column,
            text_columns=text_columns,
            metadata_column=metadata_column,
            embedding_column=embedding_column,
            embedding_model=embedding_model,
            embedding_source_column=embedding_source_column,
        )

    @classmethod
    def connect(cls, **kwargs: Any) -> "AlloyIndex":
        """Sync wrapper around aconnect() for non-async callers."""

        return SyncRunner.run(cls.aconnect(**kwargs))

    async def close(self) -> None:
        """Close the underlying client."""

        await self._client.close()

    async def upsert(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        embedding_source_column: str | None = None,
        id_column: str | None = None,
        embedding_model: str | None = None,
    ) -> UpsertResult:
        """Upsert rows into the bound table using a configured source column."""

        source_column = embedding_source_column or self.embedding_source_column
        if not source_column:
            raise AlloyNativeQueryError(
                "embedding_source_column is required unless the index was configured with a default."
            )

        return await self._client.upsert_rows(
            table=self.table,
            rows=rows,
            embedding_source_column=source_column,
            embedding_model=embedding_model or self.embedding_model,
            embedding_column=self.embedding_column,
            id_column=id_column or self.id_column,
        )

    async def query(
        self,
        query: str,
        *,
        filters: Mapping[str, Any] | None = None,
        limit: int = 10,
        rerank: bool = False,
        rerank_model: str | None = None,
        return_columns: Sequence[str] | None = None,
        candidate_limit: int | None = None,
        join_table: str | None = None,
        left_join_column: str | None = None,
        right_join_column: str | None = None,
        join_filter: Mapping[str, Any] | None = None,
    ) -> SearchResponse:
        """Run hybrid retrieval against the bound table using index defaults."""

        return await self._client.search_hybrid(
            table=self.table,
            query=query,
            filters=filters,
            limit=limit,
            embedding_model=self.embedding_model,
            rerank=rerank,
            rerank_model=rerank_model,
            id_column=self.id_column,
            text_columns=self.text_columns,
            metadata_column=self.metadata_column,
            return_columns=return_columns,
            embedding_column=self.embedding_column,
            candidate_limit=candidate_limit,
            join_table=join_table,
            left_join_column=left_join_column,
            right_join_column=right_join_column,
            join_filter=join_filter,
        )
