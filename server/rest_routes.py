"""REST routes for HTTP clients that want to use AlloyNative over FastAPI."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def upsert_request_to_client_kwargs(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an HTTP upsert request into AlloyDBClient.upsert_rows kwargs."""

    return {
        "table": str(payload["table"]),
        "rows": [dict(item) for item in payload.get("rows", [])],
        "embedding_source_column": str(payload["embedding_source_column"]),
        "embedding_model": _optional_string(payload.get("embedding_model")),
        "embedding_column": _optional_string(payload.get("embedding_column")) or "embedding",
        "id_column": _optional_string(payload.get("id_column")),
    }


def search_request_to_client_kwargs(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an HTTP search request into AlloyDBClient.search_hybrid kwargs."""

    return {
        "table": str(payload["table"]),
        "query": str(payload["query"]),
        "filters": dict(payload.get("filters", {})) if payload.get("filters") is not None else None,
        "join_filter": dict(payload.get("join_filter", {}))
        if payload.get("join_filter") is not None
        else None,
        "limit": int(payload.get("limit", 10)),
        "rerank": bool(payload.get("rerank", False)),
        "embedding_model": _optional_string(payload.get("embedding_model")),
        "rerank_model": _optional_string(payload.get("rerank_model")),
        "id_column": _optional_string(payload.get("id_column")) or "id",
        "text_columns": _coerce_string_list(payload.get("text_columns")) or ["content"],
        "metadata_column": _optional_string(payload.get("metadata_column")),
        "return_columns": _coerce_string_list(payload.get("return_columns")),
        "embedding_column": _optional_string(payload.get("embedding_column")) or "embedding",
        "candidate_limit": _optional_int(payload.get("candidate_limit")),
        "join_table": _optional_string(payload.get("join_table")),
        "left_join_column": _optional_string(payload.get("left_join_column")),
        "right_join_column": _optional_string(payload.get("right_join_column")),
    }


def create_rest_app(client=None, action_registry=None):
    """Create the FastAPI app lazily so importing this module needs no server deps."""

    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(
            "FastAPI is not installed. Install server dependencies before creating the REST app."
        ) from exc

    app = FastAPI(title="AlloyNative", version="0.1.0")

    def resolve_client():
        return client if client is not None else app.state.client

    def resolve_action_registry():
        return action_registry if action_registry is not None else app.state.action_registry

    try:
        from fastapi.staticfiles import StaticFiles
        import os
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
    except ImportError:
        pass

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def root():
        try:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/static/index.html")
        except ImportError:
            return {"message": "AlloyNative API is running."}

    @app.get("/api/dashboard")
    async def dashboard() -> dict[str, Any]:
        try:
            from server.dashboard_runtime import get_dashboard_payload

            settings = getattr(app.state, "settings", None)
            return await get_dashboard_payload(resolve_client(), settings)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/run-test")
    async def run_test(scenario: str) -> dict[str, Any]:
        try:
            from server.dashboard_runtime import run_scenario_test

            return await run_scenario_test(resolve_client(), scenario)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/upsert")
    async def upsert(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await resolve_client().upsert_rows(**upsert_request_to_client_kwargs(payload))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"count": result.count, "ids": result.ids}

    @app.post("/v1/search")
    async def search(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await resolve_client().search_hybrid(**search_request_to_client_kwargs(payload))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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

    @app.post("/v1/actions/register")
    async def register_action(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            action = resolve_action_registry().register(
                action_id=str(payload["action_id"]),
                sql=str(payload["sql"]),
                description=str(payload.get("description", "")),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "action_id": action.action_id,
            "description": action.description,
        }

    @app.post("/v1/actions/execute")
    async def execute_action(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = await resolve_action_registry().execute(
                resolve_client(),
                action_id=str(payload["action_id"]),
                params=dict(payload.get("params", {})),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"rows": rows}

    return app


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _coerce_string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("Expected a sequence of strings.")
    return [str(item) for item in value]
