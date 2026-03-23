"""SQL builders for AlloyNative's in-database embedding and retrieval flows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .errors import AlloyNativeQueryError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SUPPORTED_FILTER_OPERATORS = {
    "eq": "=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "ne": "!=",
}


@dataclass(frozen=True, slots=True)
class SQLStatement:
    """A parameterized SQL statement ready for execution."""

    sql: str
    params: dict[str, Any]


def quote_identifier(identifier: str) -> str:
    """Validate and quote a SQL identifier."""

    if not _IDENTIFIER_RE.match(identifier):
        raise AlloyNativeQueryError(
            f"Unsupported identifier '{identifier}'. Only simple SQL identifiers are allowed."
        )
    return f'"{identifier}"'


def _quote_identifiers(identifiers: Sequence[str]) -> list[str]:
    if not identifiers:
        raise AlloyNativeQueryError("At least one column must be provided.")
    return [quote_identifier(identifier) for identifier in identifiers]


def _qualified_identifier(identifier: str, *, table_alias: str | None = None) -> str:
    column_sql = quote_identifier(identifier)
    if not table_alias:
        return column_sql
    return f"{table_alias}.{column_sql}"


def build_text_expression(text_columns: Sequence[str], *, table_alias: str | None = None) -> str:
    """Build a text expression by concatenating one or more columns."""

    column_sql = [_qualified_identifier(identifier, table_alias=table_alias) for identifier in text_columns]
    coalesced = [f"COALESCE({column}::text, '')" for column in column_sql]
    return f"concat_ws(' ', {', '.join(coalesced)})"


def build_payload_expression(
    *,
    return_columns: Sequence[str] | None,
    metadata_column: str | None,
    table_alias: str | None = None,
) -> str:
    """Build a JSONB payload expression from requested return columns."""

    fragments: list[str] = []
    if metadata_column:
        fragments.append(
            f"COALESCE({_qualified_identifier(metadata_column, table_alias=table_alias)}, '{{}}'::jsonb)"
        )

    if return_columns:
        pieces: list[str] = []
        for column in return_columns:
            column_sql = _qualified_identifier(column, table_alias=table_alias)
            pieces.append(f"'{column}'")
            pieces.append(column_sql)
        fragments.append(f"jsonb_build_object({', '.join(pieces)})")

    if not fragments:
        return "'{}'::jsonb"

    expression = fragments[0]
    for fragment in fragments[1:]:
        expression = f"({expression}) || ({fragment})"
    return expression


def build_filter_clause(
    filters: Mapping[str, Any] | None,
    *,
    table_alias: str | None = None,
    param_prefix: str = "filter",
) -> tuple[str, dict[str, Any]]:
    """Build a SQL WHERE clause for supported filter operators."""

    if not filters:
        return "", {}

    clauses: list[str] = []
    params: dict[str, Any] = {}

    for index, (raw_key, value) in enumerate(filters.items()):
        if "__" in raw_key:
            column_name, operator_name = raw_key.rsplit("__", 1)
        else:
            column_name, operator_name = raw_key, "eq"

        column_sql = _qualified_identifier(column_name, table_alias=table_alias)

        if operator_name == "in":
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                raise AlloyNativeQueryError(
                    f"Filter '{raw_key}' expects a sequence for the '__in' operator."
                )
            if not value:
                raise AlloyNativeQueryError(
                    f"Filter '{raw_key}' cannot use an empty sequence for '__in'."
                )
            placeholder_names: list[str] = []
            for offset, item in enumerate(value):
                param_name = f"{param_prefix}_{index}_{offset}"
                params[param_name] = item
                placeholder_names.append(f":{param_name}")
            clauses.append(f"{column_sql} IN ({', '.join(placeholder_names)})")
            continue

        operator_sql = _SUPPORTED_FILTER_OPERATORS.get(operator_name)
        if operator_sql is None:
            supported = ", ".join(sorted(list(_SUPPORTED_FILTER_OPERATORS) + ["in"]))
            raise AlloyNativeQueryError(
                f"Unsupported filter operator '{operator_name}'. Supported operators: {supported}."
            )

        param_name = f"{param_prefix}_{index}"
        params[param_name] = value
        clauses.append(f"{column_sql} {operator_sql} :{param_name}")

    return " AND ".join(clauses), params


def build_upsert_raw_text_statement(
    *,
    table: str,
    texts: Sequence[str],
    metadata: Sequence[Mapping[str, Any]] | None,
    embedding_model: str,
    content_column: str = "content",
    metadata_column: str = "metadata",
    embedding_column: str = "embedding",
    id_column: str | None = None,
    ids: Sequence[str] | None = None,
) -> SQLStatement:
    """Build a single parameterized INSERT/UPSERT statement."""

    if not texts:
        raise AlloyNativeQueryError("texts must contain at least one item.")

    if metadata is None:
        metadata = [{} for _ in texts]

    if len(texts) != len(metadata):
        raise AlloyNativeQueryError("texts and metadata must have the same length.")

    if ids is not None and len(ids) != len(texts):
        raise AlloyNativeQueryError("ids and texts must have the same length when ids are provided.")

    table_sql = quote_identifier(table)
    content_column_sql = quote_identifier(content_column)
    metadata_column_sql = quote_identifier(metadata_column)
    embedding_column_sql = quote_identifier(embedding_column)

    columns = [content_column_sql, metadata_column_sql, embedding_column_sql]
    params: dict[str, Any] = {"embedding_model": embedding_model}

    if id_column and ids is not None:
        id_column_sql = quote_identifier(id_column)
        columns.insert(0, id_column_sql)
    else:
        id_column_sql = None

    values_sql: list[str] = []
    for index, text_value in enumerate(texts):
        params[f"content_{index}"] = text_value
        params[f"metadata_{index}"] = json.dumps(dict(metadata[index]))
        row_values = [
            f":content_{index}",
            f"CAST(:metadata_{index} AS jsonb)",
            f"google_ml.embedding(:embedding_model, :content_{index})::vector",
        ]
        if id_column_sql is not None and ids is not None:
            params[f"id_{index}"] = ids[index]
            row_values.insert(0, f":id_{index}")
        values_sql.append(f"({', '.join(row_values)})")

    sql = f"INSERT INTO {table_sql} ({', '.join(columns)}) VALUES {', '.join(values_sql)}"

    if id_column_sql is not None:
        sql += (
            f" ON CONFLICT ({id_column_sql}) DO UPDATE SET "
            f"{content_column_sql} = EXCLUDED.{content_column_sql}, "
            f"{metadata_column_sql} = EXCLUDED.{metadata_column_sql}, "
            f"{embedding_column_sql} = EXCLUDED.{embedding_column_sql}"
            f" RETURNING CAST({id_column_sql} AS TEXT) AS id"
        )

    return SQLStatement(sql=sql, params=params)


def build_upsert_rows_statement(
    *,
    table: str,
    rows: Sequence[Mapping[str, Any]],
    embedding_source_column: str,
    embedding_model: str,
    embedding_column: str = "embedding",
    id_column: str | None = None,
) -> SQLStatement:
    """Build a schema-agnostic upsert that embeds one source column per row."""

    if not rows:
        raise AlloyNativeQueryError("rows must contain at least one item.")

    first_row_keys = list(rows[0].keys())
    if not first_row_keys:
        raise AlloyNativeQueryError("Each row must contain at least one column.")

    if embedding_source_column not in rows[0]:
        raise AlloyNativeQueryError(
            f"embedding_source_column '{embedding_source_column}' must exist in every row."
        )

    for row in rows[1:]:
        if list(row.keys()) != first_row_keys:
            raise AlloyNativeQueryError(
                "All rows must use the same column set and key order."
            )
        if embedding_source_column not in row:
            raise AlloyNativeQueryError(
                f"embedding_source_column '{embedding_source_column}' must exist in every row."
            )

    if embedding_column in first_row_keys:
        raise AlloyNativeQueryError(
            f"Rows must not include the embedding column '{embedding_column}' directly."
        )

    table_sql = quote_identifier(table)
    row_column_sql = _quote_identifiers(first_row_keys)
    embedding_column_sql = quote_identifier(embedding_column)

    insert_columns = [*row_column_sql, embedding_column_sql]
    params: dict[str, Any] = {"embedding_model": embedding_model}
    values_sql: list[str] = []

    for row_index, row in enumerate(rows):
        row_placeholders: list[str] = []
        for column_index, column_name in enumerate(first_row_keys):
            param_name = f"row_{row_index}_{column_index}"
            value = row[column_name]
            if isinstance(value, (Mapping, list, tuple)):
                params[param_name] = json.dumps(value)
                row_placeholders.append(f"CAST(:{param_name} AS jsonb)")
            else:
                params[param_name] = value
                row_placeholders.append(f":{param_name}")
        source_param = f"row_{row_index}_{first_row_keys.index(embedding_source_column)}"
        row_placeholders.append(
            f"google_ml.embedding(:embedding_model, :{source_param})::vector"
        )
        values_sql.append(f"({', '.join(row_placeholders)})")

    sql = (
        f"INSERT INTO {table_sql} ({', '.join(insert_columns)}) "
        f"VALUES {', '.join(values_sql)}"
    )

    if id_column:
        id_column_sql = quote_identifier(id_column)
        update_assignments = [
            f"{quote_identifier(column_name)} = EXCLUDED.{quote_identifier(column_name)}"
            for column_name in first_row_keys
            if column_name != id_column
        ]
        update_assignments.append(
            f"{embedding_column_sql} = EXCLUDED.{embedding_column_sql}"
        )
        sql += (
            f" ON CONFLICT ({id_column_sql}) DO UPDATE SET "
            f"{', '.join(update_assignments)}"
            f" RETURNING CAST({id_column_sql} AS TEXT) AS id"
        )

    return SQLStatement(sql=sql, params=params)


def build_search_hybrid_statement(
    *,
    table: str,
    query: str,
    filters: Mapping[str, Any] | None,
    limit: int,
    embedding_model: str,
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
) -> SQLStatement:
    """Build the hybrid search query, with optional LLM reranking."""

    if limit < 1:
        raise AlloyNativeQueryError("limit must be at least 1.")

    table_sql = quote_identifier(table)
    text_columns = list(text_columns or ["content"])

    has_join = any(
        value is not None
        for value in (join_table, left_join_column, right_join_column, join_filter)
    )
    if has_join and not join_table:
        raise AlloyNativeQueryError(
            "join_table is required when join columns or join_filter are provided."
        )
    if join_table and (not left_join_column or not right_join_column):
        raise AlloyNativeQueryError(
            "left_join_column and right_join_column are required when join_table is provided."
        )

    if join_table:
        base_alias = "base"
        joined_alias = "joined"
        from_clause = (
            f"FROM {table_sql} AS {base_alias} "
            f"INNER JOIN {quote_identifier(join_table)} AS {joined_alias} "
            f"ON {_qualified_identifier(left_join_column, table_alias=base_alias)} "
            f"= {_qualified_identifier(right_join_column, table_alias=joined_alias)}"
        )
        id_column_sql = _qualified_identifier(id_column, table_alias=base_alias)
        embedding_column_sql = _qualified_identifier(embedding_column, table_alias=base_alias)
        text_expression = build_text_expression(text_columns, table_alias=base_alias)
        payload_expression = build_payload_expression(
            return_columns=return_columns,
            metadata_column=metadata_column,
            table_alias=base_alias,
        )
        base_filter_sql, base_filter_params = build_filter_clause(
            filters,
            table_alias=base_alias,
            param_prefix="filter",
        )
        join_filter_sql, join_filter_params = build_filter_clause(
            join_filter,
            table_alias=joined_alias,
            param_prefix="join_filter",
        )
    else:
        from_clause = f"FROM {table_sql}"
        id_column_sql = quote_identifier(id_column)
        embedding_column_sql = quote_identifier(embedding_column)
        text_expression = build_text_expression(text_columns)
        payload_expression = build_payload_expression(
            return_columns=return_columns,
            metadata_column=metadata_column,
        )
        base_filter_sql, base_filter_params = build_filter_clause(filters)
        join_filter_sql, join_filter_params = "", {}

    combined_filters = " AND ".join(
        clause for clause in (base_filter_sql, join_filter_sql) if clause
    )
    where_clause = f"WHERE {combined_filters}" if combined_filters else ""

    final_candidate_limit = candidate_limit or max(limit * 5, 50)
    params: dict[str, Any] = {
        "query_text": query,
        "embedding_model": embedding_model,
        "limit": limit,
        "candidate_limit": final_candidate_limit,
        **base_filter_params,
        **join_filter_params,
    }

    base_candidates = f"""
WITH vector_search AS (
    SELECT
        CAST({id_column_sql} AS TEXT) AS id,
        {text_expression} AS content,
        {payload_expression} AS payload,
        {embedding_column_sql} <=> google_ml.embedding(:embedding_model, :query_text)::vector AS distance,
        ROW_NUMBER() OVER (
            ORDER BY {embedding_column_sql} <=> google_ml.embedding(:embedding_model, :query_text)::vector
        ) AS rank
    {from_clause}
    {where_clause}
    LIMIT :candidate_limit
),
text_search AS (
    SELECT
        CAST({id_column_sql} AS TEXT) AS id,
        {text_expression} AS content,
        {payload_expression} AS payload,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank(
                to_tsvector('english', {text_expression}),
                plainto_tsquery('english', :query_text)
            ) DESC
        ) AS rank
    {from_clause}
    {f'{where_clause} AND' if where_clause else 'WHERE'}
        to_tsvector('english', {text_expression}) @@ plainto_tsquery('english', :query_text)
    LIMIT :candidate_limit
),
rrf AS (
    SELECT
        COALESCE(v.id, t.id) AS id,
        COALESCE(v.content, t.content) AS content,
        COALESCE(v.payload, t.payload) AS payload,
        COALESCE(v.distance, 1.0) AS distance,
        (1.0 / (60 + COALESCE(v.rank, 1000)))
        + (1.0 / (60 + COALESCE(t.rank, 1000))) AS score
    FROM vector_search v
    FULL OUTER JOIN text_search t ON v.id = t.id
)
SELECT id, content, payload, distance, score
FROM rrf
ORDER BY score DESC, distance ASC
LIMIT :candidate_limit
""".strip()

    if not rerank:
        return SQLStatement(
            sql=(
                "WITH candidates AS ("
                + base_candidates
                + ") SELECT id, content, payload, distance, score "
                + "FROM candidates ORDER BY score DESC, distance ASC LIMIT :limit"
            ),
            params=params,
        )

    if not rerank_model:
        raise AlloyNativeQueryError("rerank_model is required when rerank=True.")

    params["rerank_model"] = rerank_model
    rerank_sql = f"""
WITH candidates AS (
    {base_candidates}
),
reranked AS (
    SELECT
        id,
        content,
        payload,
        distance,
        COALESCE(
            NULLIF(
                regexp_replace(
                    (
                        google_ml.predict_row(
                            :rerank_model,
                            json_build_object(
                                'contents',
                                json_build_array(
                                    json_build_object(
                                        'role', 'user',
                                        'parts',
                                        json_build_array(
                                            json_build_object(
                                                'text',
                                                'Rate the relevance of the candidate passage to the query on a scale from 0 to 100. '
                                                || 'Return only the numeric score. Query: '
                                                || :query_text
                                                || E'\\nCandidate: '
                                                || content
                                            )
                                        )
                                    )
                                ),
                                'generationConfig',
                                json_build_object(
                                    'temperature', 0.0,
                                    'maxOutputTokens', 16
                                )
                            )
                        )::jsonb -> 0 -> 'candidates' -> 0 -> 'content' -> 'parts' -> 0 ->> 'text'
                    ),
                    '[^0-9.]',
                    '',
                    'g'
                ),
                ''
            )::double precision,
            0.0
        ) AS score
    FROM candidates
)
SELECT id, content, payload, distance, score
FROM reranked
ORDER BY score DESC, distance ASC
LIMIT :limit
""".strip()
    return SQLStatement(sql=rerank_sql, params=params)
