"""Tests for AlloyNative environment validation."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from alloynative.config import AlloyDBConfig
from alloynative.validation import validate_environment


class ValidationTest(IsolatedAsyncioTestCase):
    """Validate the happy path without requiring a live database."""

    async def test_validate_environment_returns_report(self) -> None:
        connection_manager = AsyncMock()
        connection_manager.fetch_val.side_effect = [
            "1.5.9",
            "0.8.1.google-1",
            "on",
            "on",
            1,
        ]

        report = await validate_environment(
            connection_manager,
            AlloyDBConfig(
                project_id="project",
                region="us-central1",
                cluster="cluster",
                instance="instance",
                database="postgres",
            ),
        )

        self.assertEqual(report.google_ml_extension_version, "1.5.9")
        self.assertEqual(report.vector_extension_version, "0.8.1.google-1")
        self.assertTrue(report.model_support_enabled)
        self.assertTrue(report.ai_query_engine_enabled)
        self.assertTrue(report.default_embedding_model_available)
