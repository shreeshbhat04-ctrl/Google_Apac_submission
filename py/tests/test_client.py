"""Tests for the public AlloyNative client surface."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from alloynative.capabilities import CapabilitySnapshot
from alloynative.client import AlloyDBClient
from alloynative.config import AlloyDBConfig
from alloynative.index import AlloyIndex
from alloynative.errors import AlloyNativeQueryError
from alloynative.results import SearchResponse, UpsertResult


class AlloyDBClientTest(IsolatedAsyncioTestCase):
    """Exercise the client surface with a mocked connection manager."""

    async def test_aconnect_connects_and_validates(self) -> None:
        connection_manager = AsyncMock()
        validator = AsyncMock(return_value="validated")

        client = await AlloyDBClient.aconnect(
            project_id="project",
            region="us-central1",
            cluster="cluster",
            instance="instance",
            database="postgres",
            db_user="svc@example.com",
            connection_manager=connection_manager,
            validator=validator,
        )

        connection_manager.connect.assert_awaited_once()
        validator.assert_awaited_once()
        self.assertEqual(client.validation_report, "validated")

    async def test_aconnect_exposes_detected_capabilities(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.capabilities = CapabilitySnapshot(
            has_pgvector=True,
            has_scann=True,
            preferred_index_type="scann",
        )
        validator = AsyncMock(return_value="validated")

        client = await AlloyDBClient.aconnect(
            project_id="project",
            region="us-central1",
            cluster="cluster",
            instance="instance",
            database="postgres",
            connection_manager=connection_manager,
            validator=validator,
        )

        self.assertTrue(client.capabilities.has_scann)
        self.assertEqual(client.capabilities.preferred_index_type, "scann")

    async def test_execute_delegates_to_connection_manager(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.execute.return_value = [{"value": 1}]
        client = AlloyDBClient(
            AlloyDBConfig(
                project_id="project",
                region="us-central1",
                cluster="cluster",
                instance="instance",
                database="postgres",
            ),
            connection_manager=connection_manager,
            validator=AsyncMock(),
        )

        rows = await client.execute("SELECT 1")

        connection_manager.execute.assert_awaited_once_with("SELECT 1", None)
        self.assertEqual(rows, [{"value": 1}])

    async def test_upsert_raw_text_returns_count_and_ids(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.fetch_all.return_value = [{"id": "doc-1"}]
        client = AlloyDBClient(
            AlloyDBConfig(
                project_id="project",
                region="us-central1",
                cluster="cluster",
                instance="instance",
                database="postgres",
            ),
            connection_manager=connection_manager,
            validator=AsyncMock(),
        )

        result = await client.upsert_raw_text(
            table="documents",
            texts=["hello"],
            metadata=[{"source": "demo"}],
            id_column="id",
            ids=["doc-1"],
        )

        self.assertIsInstance(result, UpsertResult)
        self.assertEqual(result.count, 1)
        self.assertEqual(result.ids, ["doc-1"])

    async def test_upsert_rows_supports_general_purpose_schema(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.fetch_all.return_value = [{"id": "1"}]
        client = AlloyDBClient(
            AlloyDBConfig(
                project_id="project",
                region="us-central1",
                cluster="cluster",
                instance="instance",
                database="postgres",
            ),
            connection_manager=connection_manager,
            validator=AsyncMock(),
        )

        result = await client.upsert_rows(
            table="products",
            rows=[
                {
                    "id": 1,
                    "name": "Shoe",
                    "description": "Lightweight trainer",
                    "category": "shoes",
                }
            ],
            embedding_source_column="description",
            id_column="id",
        )

        self.assertIsInstance(result, UpsertResult)
        self.assertEqual(result.ids, ["1"])

    async def test_search_hybrid_materializes_result_objects(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.fetch_all.return_value = [
            {
                "id": "doc-1",
                "content": "hello",
                "payload": {"source": "demo", "name": "Shoe"},
                "score": 0.98,
                "distance": 0.12,
            }
        ]
        client = AlloyDBClient(
            AlloyDBConfig(
                project_id="project",
                region="us-central1",
                cluster="cluster",
                instance="instance",
                database="postgres",
            ),
            connection_manager=connection_manager,
            validator=AsyncMock(),
        )

        response = await client.search_hybrid(
            table="documents",
            query="hello",
            filters={"category": "demo"},
            limit=5,
            text_columns=["name", "description"],
            return_columns=["name", "category"],
            metadata_column=None,
        )

        self.assertIsInstance(response, SearchResponse)
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].id, "doc-1")
        self.assertEqual(response.results[0].metadata["source"], "demo")
        self.assertEqual(response.results[0].payload["name"], "Shoe")

    async def test_search_hybrid_supports_join_aware_queries(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.fetch_all.return_value = []
        client = AlloyDBClient(
            AlloyDBConfig(
                project_id="project",
                region="us-central1",
                cluster="cluster",
                instance="instance",
                database="postgres",
            ),
            connection_manager=connection_manager,
            validator=AsyncMock(),
        )

        await client.search_hybrid(
            table="products",
            query="running shoes",
            text_columns=["name", "description"],
            join_table="inventory",
            left_join_column="id",
            right_join_column="product_id",
            join_filter={"stock__gt": 0},
        )

        connection_manager.fetch_all.assert_awaited_once()


class AlloyIndexTest(IsolatedAsyncioTestCase):
    """Exercise the Pinecone-familiar AlloyIndex wrapper."""

    async def test_upsert_requires_source_column_when_no_default_exists(self) -> None:
        client = AsyncMock()
        index = AlloyIndex(client=client, table="products")

        with self.assertRaises(AlloyNativeQueryError):
            await index.upsert([{"id": 1, "description": "demo"}])

    async def test_upsert_uses_index_defaults(self) -> None:
        client = AsyncMock()
        client.upsert_rows.return_value = UpsertResult(count=1, ids=["1"])
        client.capabilities = CapabilitySnapshot(has_pgvector=True)
        index = AlloyIndex(
            client=client,
            table="products",
            text_columns=["name", "description"],
            embedding_source_column="description",
        )

        result = await index.upsert([{"id": 1, "description": "demo"}])

        self.assertEqual(result.ids, ["1"])
        client.upsert_rows.assert_awaited_once()
        self.assertTrue(index.capabilities.has_pgvector)

    async def test_query_forwards_join_overrides(self) -> None:
        client = AsyncMock()
        client.search_hybrid.return_value = SearchResponse(results=[])
        index = AlloyIndex(
            client=client,
            table="products",
            text_columns=["name", "description"],
        )

        await index.query(
            "running shoes",
            filters={"category": "shoes"},
            join_table="inventory",
            left_join_column="id",
            right_join_column="product_id",
            join_filter={"stock__gt": 0},
        )

        client.search_hybrid.assert_awaited_once()
