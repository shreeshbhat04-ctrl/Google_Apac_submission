"""Tests for the gRPC transport adapter."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from server.grpc_servicer import AlloyNativeGRPCService


class AlloyNativeGRPCServiceTest(IsolatedAsyncioTestCase):
    """Verify request translation into AlloyDBClient calls."""

    async def test_upsert_translates_request_shape(self) -> None:
        client = AsyncMock()
        client.upsert_rows.return_value.count = 1
        client.upsert_rows.return_value.ids = ["doc-1"]
        service = AlloyNativeGRPCService(client)

        response = await service.upsert(
            {
                "table": "products",
                "rows": [{"fields": {"name": "shoe", "description": "hello"}}],
                "embedding_source_column": "description",
                "embedding_model": "text-embedding-005",
                "id_column": "id",
            }
        )

        client.upsert_rows.assert_awaited_once()
        self.assertEqual(response, {"count": 1, "ids": ["doc-1"]})

    async def test_search_translates_request_shape(self) -> None:
        client = AsyncMock()
        client.search_hybrid.return_value.results = [
            AsyncMock(
                id="doc-1",
                content="hello",
                payload={"name": "shoe"},
                metadata={"source": "demo"},
                score=0.9,
                distance=0.1,
            )
        ]
        client.search_hybrid.return_value.reranked = True
        client.search_hybrid.return_value.candidate_count = 1
        service = AlloyNativeGRPCService(client)

        response = await service.search(
            {
                "table": "products",
                "query": "hello",
                "filters": {"category": "demo"},
                "join_filter": {"stock__gt": 0},
                "limit": 5,
                "rerank": True,
                "join_table": "inventory",
                "left_join_column": "id",
                "right_join_column": "product_id",
                "text_columns": ["name", "description"],
                "return_columns": ["name", "category", "price"],
            }
        )

        client.search_hybrid.assert_awaited_once()
        self.assertTrue(response["reranked"])
        self.assertEqual(response["candidate_count"], 1)
        self.assertEqual(response["results"][0]["id"], "doc-1")
        self.assertEqual(response["results"][0]["payload"]["name"], "shoe")
