"""Tests for server settings and mock client behavior."""

import os
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock

from server.dependencies import MockAlloyDBClient, ServerSettings, build_client
from alloynative.errors import AlloyNativeConfigurationError


class ServerSettingsTest(TestCase):
    """Verify environment-backed settings support dev mode defaults."""

    def test_from_env_supports_dev_mode_defaults(self) -> None:
        original = dict(os.environ)
        try:
            os.environ["ALLOYNATIVE_DEV_MODE"] = "true"
            os.environ.pop("ALLOYNATIVE_PROJECT_ID", None)
            settings = ServerSettings.from_env()
        finally:
            os.environ.clear()
            os.environ.update(original)

        self.assertTrue(settings.dev_mode)
        self.assertEqual(settings.project_id, "local-dev-project")

    def test_from_env_requires_production_values_when_not_in_dev_mode(self) -> None:
        original = dict(os.environ)
        try:
            os.environ["ALLOYNATIVE_DEV_MODE"] = "false"
            for key in (
                "ALLOYNATIVE_PROJECT_ID",
                "ALLOYNATIVE_REGION",
                "ALLOYNATIVE_CLUSTER",
                "ALLOYNATIVE_INSTANCE",
                "ALLOYNATIVE_DATABASE",
            ):
                os.environ.pop(key, None)

            with self.assertRaises(AlloyNativeConfigurationError):
                ServerSettings.from_env()
        finally:
            os.environ.clear()
            os.environ.update(original)


class MockAlloyDBClientTest(IsolatedAsyncioTestCase):
    """Ensure the in-memory mock behaves enough like the real client for local demos."""

    async def test_upsert_and_search_round_trip(self) -> None:
        client = MockAlloyDBClient()
        await client.upsert_rows(
            table="products",
            rows=[
                {
                    "id": 1,
                    "name": "Lightweight Running Shoe",
                    "description": "Breathable daily trainer for road running",
                    "category": "shoes",
                    "price": 79.99,
                }
            ],
            embedding_source_column="description",
            id_column="id",
        )

        response = await client.search_hybrid(
            table="products",
            query="running shoe",
            filters={"category": "shoes", "price__lte": 100},
            text_columns=["name", "description"],
            return_columns=["name", "category", "price"],
            limit=5,
        )

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].payload["name"], "Lightweight Running Shoe")

    async def test_build_client_uses_mock_in_dev_mode(self) -> None:
        settings = ServerSettings(
            project_id="project",
            region="us-central1",
            cluster="cluster",
            instance="instance",
            database="db",
            dev_mode=True,
        )

        client = await build_client(settings)

        self.assertIsInstance(client, MockAlloyDBClient)

    async def test_build_client_passes_runtime_models_to_real_client(self) -> None:
        settings = ServerSettings(
            project_id="project",
            region="us-east4",
            cluster="cluster",
            instance="instance",
            database="db",
            db_user="svc@example.com",
            ip_type="PRIVATE",  # type: ignore[arg-type]
            embedding_model="text-embedding-005",
            rerank_model="gemini-2.0-flash-global",
            dev_mode=False,
        )

        from server import dependencies as dependencies_module

        original = dependencies_module.AlloyDBClient.aconnect
        dependencies_module.AlloyDBClient.aconnect = AsyncMock(return_value=AsyncMock())
        try:
            await build_client(settings)
            dependencies_module.AlloyDBClient.aconnect.assert_awaited_once_with(
                project_id="project",
                region="us-east4",
                cluster="cluster",
                instance="instance",
                database="db",
                db_user="svc@example.com",
                ip_type=settings.ip_type,
                default_embedding_model="text-embedding-005",
                default_rerank_model="gemini-2.0-flash-global",
            )
        finally:
            dependencies_module.AlloyDBClient.aconnect = original

    async def test_search_hybrid_supports_join_filters_in_mock_mode(self) -> None:
        client = MockAlloyDBClient()
        await client.upsert_rows(
            table="products",
            rows=[
                {
                    "id": 1,
                    "name": "Lightweight Running Shoe",
                    "description": "Breathable daily trainer",
                }
            ],
            embedding_source_column="description",
            id_column="id",
        )
        await client.upsert_rows(
            table="inventory",
            rows=[{"product_id": 1, "stock": 4}],
            embedding_source_column="product_id",
        )

        response = await client.search_hybrid(
            table="products",
            query="running shoe",
            text_columns=["name", "description"],
            join_table="inventory",
            left_join_column="id",
            right_join_column="product_id",
            join_filter={"stock__gt": 0},
        )

        self.assertEqual(len(response.results), 1)
