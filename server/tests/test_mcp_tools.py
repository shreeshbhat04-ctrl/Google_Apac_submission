"""Tests for MCP-friendly wrappers around the AlloyNative client."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from server.action_registry import ActionRegistry
from server.mcp_tools import AlloyNativeMCPTools


class AlloyNativeMCPToolsTest(IsolatedAsyncioTestCase):
    """Verify the MCP wrappers stay thin and delegate to the SDK."""

    async def test_upsert_rows_delegates_to_client(self) -> None:
        client = AsyncMock()
        client.upsert_rows.return_value.count = 1
        client.upsert_rows.return_value.ids = ["1"]
        tools = AlloyNativeMCPTools(client, ActionRegistry())

        response = await tools.upsert_rows(
            table="products",
            rows=[{"id": 1, "description": "demo"}],
            embedding_source_column="description",
            id_column="id",
        )

        client.upsert_rows.assert_awaited_once()
        self.assertEqual(response["ids"], ["1"])

    async def test_register_and_execute_action_round_trips(self) -> None:
        client = AsyncMock()
        client.execute.return_value = [{"updated": 1}]
        tools = AlloyNativeMCPTools(client, ActionRegistry())

        register_response = await tools.register_action(
            action_id="freeze_account",
            sql="UPDATE accounts SET frozen = true WHERE id = :account_id RETURNING id",
            description="Freeze an account by id.",
        )
        execute_response = await tools.execute_action(
            action_id="freeze_account",
            params={"account_id": "acct-1"},
        )

        self.assertEqual(register_response["action_id"], "freeze_account")
        self.assertEqual(execute_response["rows"], [{"updated": 1}])
