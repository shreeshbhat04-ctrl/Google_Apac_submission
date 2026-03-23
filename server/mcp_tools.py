"""MCP-friendly wrappers around the AlloyNative Python client."""

from __future__ import annotations

from typing import Any


class AlloyNativeMCPTools:
    """Expose the AlloyNative client as a set of simple async tool methods."""

    def __init__(self, client, action_registry) -> None:
        self._client = client
        self._action_registry = action_registry

    async def search_documents(
        self,
        *,
        table: str,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        rerank: bool = False,
        text_columns: list[str] | None = None,
        return_columns: list[str] | None = None,
        metadata_column: str | None = None,
        embedding_column: str = "embedding",
        join_table: str | None = None,
        left_join_column: str | None = None,
        right_join_column: str | None = None,
        join_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search a table using hybrid retrieval and optional reranking."""

        response = await self._client.search_hybrid(
            table=table,
            query=query,
            filters=filters,
            limit=limit,
            rerank=rerank,
            text_columns=text_columns,
            return_columns=return_columns,
            metadata_column=metadata_column,
            embedding_column=embedding_column,
            join_table=join_table,
            left_join_column=left_join_column,
            right_join_column=right_join_column,
            join_filter=join_filter,
        )
        return [
            {
                "id": result.id,
                "content": result.content,
                "payload": result.payload,
                "metadata": result.metadata,
                "score": result.score,
                "distance": result.distance,
            }
            for result in response.results
        ]

    async def upsert_rows(
        self,
        *,
        table: str,
        rows: list[dict[str, Any]],
        embedding_source_column: str,
        embedding_column: str = "embedding",
        id_column: str | None = None,
        embedding_model: str | None = None,
    ) -> dict[str, Any]:
        """Insert or upsert arbitrary rows while generating embeddings in AlloyDB."""

        result = await self._client.upsert_rows(
            table=table,
            rows=rows,
            embedding_source_column=embedding_source_column,
            embedding_model=embedding_model,
            embedding_column=embedding_column,
            id_column=id_column,
        )
        return {"count": result.count, "ids": result.ids}

    async def register_action(
        self, *, action_id: str, sql: str, description: str = ""
    ) -> dict[str, str]:
        """Register a SQL action that can be triggered later."""

        action = self._action_registry.register(
            action_id=action_id,
            sql=sql,
            description=description,
        )
        return {"action_id": action.action_id, "description": action.description}

    async def execute_action(
        self, *, action_id: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a previously registered SQL action."""

        rows = await self._action_registry.execute(
            self._client,
            action_id=action_id,
            params=params or {},
        )
        return {"rows": rows}
