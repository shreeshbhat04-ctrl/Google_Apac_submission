"""Thin transport adapter between the shared RPC contract and AlloyDBClient."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from alloynative import AlloyDBClient


class AlloyNativeGRPCService:
    """Translate RPC-shaped payloads into AlloyDBClient method calls."""

    def __init__(self, client: AlloyDBClient) -> None:
        self._client = client

    async def upsert(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Handle an UpsertRequest-like payload."""

        rows = _coerce_rows(request.get("rows"))
        result = await self._client.upsert_rows(
            table=str(request["table"]),
            rows=rows,
            embedding_source_column=str(request["embedding_source_column"]),
            embedding_model=_optional_string(request.get("embedding_model")),
            embedding_column=_optional_string(request.get("embedding_column")) or "embedding",
            id_column=_optional_string(request.get("id_column")),
        )
        return {"count": result.count, "ids": result.ids}

    async def search(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Handle a SearchRequest-like payload."""

        response = await self._client.search_hybrid(
            table=str(request["table"]),
            query=str(request["query"]),
            filters=_coerce_filters(request.get("filters")),
            limit=int(request.get("limit", 10)),
            rerank=bool(request.get("rerank", False)),
            embedding_model=_optional_string(request.get("embedding_model")),
            rerank_model=_optional_string(request.get("rerank_model")),
            id_column=_optional_string(request.get("id_column")) or "id",
            text_columns=_coerce_string_list(request.get("text_columns")) or ["content"],
            metadata_column=_optional_string(request.get("metadata_column")),
            return_columns=_coerce_string_list(request.get("return_columns")),
            embedding_column=_optional_string(request.get("embedding_column")) or "embedding",
            candidate_limit=_optional_int(request.get("candidate_limit")),
            join_filter=_coerce_filters(request.get("join_filter")),
            join_table=_optional_string(request.get("join_table")),
            left_join_column=_optional_string(request.get("left_join_column")),
            right_join_column=_optional_string(request.get("right_join_column")),
        )
        return {
            "results": [
                {
                    "id": result.id,
                    "content": result.content,
                    "payload": result.payload,
                    "metadata": result.metadata,
                    "score": result.score,
                    "distance": result.distance,
                }
                for result in response.results
            ],
            "reranked": response.reranked,
            "candidate_count": response.candidate_count,
        }


def _coerce_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if raw_rows is None:
        return []
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise TypeError("rows must be a sequence of row objects.")

    rows: list[dict[str, Any]] = []
    for item in raw_rows:
        if not isinstance(item, Mapping):
            raise TypeError("Each row must be a mapping-like object.")
        if "fields" in item and isinstance(item["fields"], Mapping):
            rows.append(dict(item["fields"]))
        else:
            rows.append(dict(item))
    return rows


def _coerce_filters(raw_filters: Any) -> dict[str, Any] | None:
    if raw_filters is None:
        return None
    if isinstance(raw_filters, Mapping):
        return dict(raw_filters)
    raise TypeError("filters must be mapping-like when provided.")


def _coerce_string_list(raw_values: Any) -> list[str] | None:
    if raw_values is None:
        return None
    if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
        raise TypeError("ids must be a sequence of strings.")
    return [str(item) for item in raw_values]


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
