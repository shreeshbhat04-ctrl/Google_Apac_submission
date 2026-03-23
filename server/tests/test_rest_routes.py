"""Tests for REST request shaping helpers."""

from unittest import TestCase
from unittest.mock import AsyncMock

from server.rest_routes import create_rest_app, search_request_to_client_kwargs, upsert_request_to_client_kwargs


class RestRouteHelpersTest(TestCase):
    """Verify REST payloads map cleanly into AlloyDBClient kwargs."""

    def test_upsert_request_to_client_kwargs_supports_general_rows(self) -> None:
        kwargs = upsert_request_to_client_kwargs(
            {
                "table": "products",
                "rows": [{"id": 1, "name": "shoe", "description": "demo"}],
                "embedding_source_column": "description",
                "id_column": "id",
            }
        )

        self.assertEqual(kwargs["table"], "products")
        self.assertEqual(kwargs["embedding_source_column"], "description")
        self.assertEqual(kwargs["rows"][0]["name"], "shoe")

    def test_search_request_to_client_kwargs_supports_multi_column_search(self) -> None:
        kwargs = search_request_to_client_kwargs(
            {
                "table": "products",
                "query": "running shoes",
                "filters": {"category": "shoes", "price__lte": 100},
                "join_filter": {"stock__gt": 0},
                "join_table": "inventory",
                "left_join_column": "id",
                "right_join_column": "product_id",
                "text_columns": ["name", "description"],
                "return_columns": ["name", "category", "price"],
                "metadata_column": "metadata",
            }
        )

        self.assertEqual(kwargs["text_columns"], ["name", "description"])
        self.assertEqual(kwargs["return_columns"], ["name", "category", "price"])
        self.assertEqual(kwargs["filters"]["category"], "shoes")
        self.assertEqual(kwargs["join_filter"]["stock__gt"], 0)
        self.assertEqual(kwargs["join_table"], "inventory")

    def test_create_rest_app_returns_fastapi_app_when_dependency_available(self) -> None:
        app = create_rest_app(AsyncMock(), AsyncMock())
        self.assertEqual(app.title, "AlloyNative")
