"""Registry for SQL-backed actions that agents or HTTP clients can trigger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RegisteredAction:
    """A SQL action that can be executed later with parameters."""

    action_id: str
    sql: str
    description: str = ""


class ActionRegistry:
    """Store and execute named SQL actions using the AlloyNative client."""

    def __init__(self) -> None:
        self._actions: dict[str, RegisteredAction] = {}

    def register(self, action_id: str, sql: str, description: str = "") -> RegisteredAction:
        """Register or replace a named action."""

        action = RegisteredAction(action_id=action_id, sql=sql, description=description)
        self._actions[action_id] = action
        return action

    def get(self, action_id: str) -> RegisteredAction:
        """Fetch a previously registered action."""

        try:
            return self._actions[action_id]
        except KeyError as exc:
            raise KeyError(f"Unknown action_id '{action_id}'.") from exc

    def list_actions(self) -> list[RegisteredAction]:
        """Return all registered actions."""

        return list(self._actions.values())

    async def execute(self, client, action_id: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a named action through the AlloyNative client."""

        action = self.get(action_id)
        return await client.execute(action.sql, params or {})
