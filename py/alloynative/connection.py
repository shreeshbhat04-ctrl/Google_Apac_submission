"""Connection management for AlloyNative's async AlloyDB access path."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .auth import resolve_db_user
from .capabilities import CapabilitySnapshot, DEFAULT_CAPABILITIES
from .config import AlloyDBConfig
from .errors import AlloyNativeConnectionError


class AlloyDBConnectionManager:
    """Manage an async SQLAlchemy engine backed by the AlloyDB connector."""

    def __init__(self, config: AlloyDBConfig, *, db_user_resolver=resolve_db_user) -> None:
        self._config = config
        self._db_user_resolver = db_user_resolver
        self._connector: Any | None = None
        self._engine: Any | None = None
        self._capabilities = DEFAULT_CAPABILITIES

    @property
    def connected(self) -> bool:
        """Return whether the connection manager has created its engine."""

        return self._engine is not None

    @property
    def capabilities(self) -> CapabilitySnapshot:
        """Expose detected vector/index capabilities for the connected instance."""

        return self._capabilities

    async def connect(self) -> None:
        """Create the connector and async engine, then verify connectivity."""

        if self._engine is not None:
            return

        try:
            from google.cloud.alloydb.connector import (  # type: ignore[import-not-found]
                AsyncConnector,
                IPTypes,
                RefreshStrategy,
            )
            from sqlalchemy import text  # type: ignore[import-not-found]
            from sqlalchemy.ext.asyncio import (  # type: ignore[import-not-found]
                create_async_engine,
            )
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise AlloyNativeConnectionError(
                "Missing runtime dependencies for AlloyNative connections. "
                "Install google-cloud-alloydb-connector[asyncpg] and sqlalchemy."
            ) from exc

        db_user = self._db_user_resolver(self._config.db_user)

        try:
            ip_type = getattr(IPTypes, self._config.ip_type.value)
            refresh_strategy = getattr(RefreshStrategy, self._config.refresh_strategy)
            self._connector = AsyncConnector(
                user_agent=self._config.user_agent,
                refresh_strategy=refresh_strategy,
            )

            async def get_connection() -> Any:
                return await self._connector.connect(
                    self._config.instance_uri,
                    "asyncpg",
                    user=db_user,
                    db=self._config.database,
                    enable_iam_auth=self._config.enable_iam_auth,
                    ip_type=ip_type,
                )

            self._engine = create_async_engine(
                "postgresql+asyncpg://",
                async_creator=get_connection,
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
                pool_pre_ping=True,
            )

            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                self._capabilities = await self._detect_capabilities(conn)
        except Exception as exc:
            await self.close()
            raise AlloyNativeConnectionError(
                "Failed to connect to AlloyDB using the configured connector settings."
            ) from exc

    async def close(self) -> None:
        """Dispose of the engine and connector cleanly."""

        engine = self._engine
        connector = self._connector
        self._engine = None
        self._connector = None
        self._capabilities = DEFAULT_CAPABILITIES

        if engine is not None:
            await engine.dispose()
        if connector is not None:
            await connector.close()

    async def execute(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute SQL and materialize any returned rows as dictionaries."""

        await self.connect()

        try:
            from sqlalchemy import text  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise AlloyNativeConnectionError(
                "sqlalchemy is required to execute queries through AlloyNative."
            ) from exc

        assert self._engine is not None

        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text(sql), dict(params or {}))
                if result.returns_rows:
                    return [dict(row) for row in result.mappings().all()]
                return []
        except Exception as exc:
            raise AlloyNativeConnectionError("Query execution failed.") from exc

    async def fetch_all(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows."""

        return await self.execute(sql, params)

    async def fetch_one(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Execute a query and return the first row if present."""

        rows = await self.execute(sql, params)
        return rows[0] if rows else None

    async def fetch_val(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> Any | None:
        """Execute a query and return the first column of the first row."""

        row = await self.fetch_one(sql, params)
        if row is None:
            return None
        return next(iter(row.values()))

    async def _detect_capabilities(self, conn: Any) -> CapabilitySnapshot:
        """Detect optional vector/index features without failing the connection."""

        try:
            from sqlalchemy import text  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise AlloyNativeConnectionError(
                "sqlalchemy is required to inspect AlloyDB capabilities."
            ) from exc

        result = await conn.execute(
            text(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname IN ('vector', 'alloydb_scann')
                """
            )
        )
        extensions = {str(row[0]) for row in result.fetchall()}
        return CapabilitySnapshot.from_extensions(extensions)
