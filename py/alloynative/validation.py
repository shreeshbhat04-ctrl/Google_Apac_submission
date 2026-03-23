"""Environment validation checks for AlloyNative-supported AlloyDB instances."""

from __future__ import annotations

from dataclasses import dataclass

from .config import AlloyDBConfig
from .errors import AlloyNativeModelError, AlloyNativeValidationError


@dataclass(slots=True)
class ValidationReport:
    """Summary of environment checks performed during connect()."""

    google_ml_extension_version: str
    vector_extension_version: str
    model_support_enabled: bool
    ai_query_engine_enabled: bool
    default_embedding_model_available: bool


async def validate_environment(connection_manager, config: AlloyDBConfig) -> ValidationReport:
    """Validate extensions, flags, and model availability before SDK use."""

    errors: list[str] = []

    google_ml_extension_version = await connection_manager.fetch_val(
        "SELECT extversion FROM pg_extension WHERE extname = 'google_ml_integration'"
    )
    if not google_ml_extension_version:
        errors.append("Extension 'google_ml_integration' is not installed.")

    vector_extension_version = await connection_manager.fetch_val(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    )
    if not vector_extension_version:
        errors.append("Extension 'vector' is not installed.")

    model_support_value = await connection_manager.fetch_val(
        "SELECT setting FROM pg_settings "
        "WHERE name = 'google_ml_integration.enable_model_support'"
    )
    model_support_enabled = model_support_value == "on"
    if config.require_model_support and not model_support_enabled:
        errors.append(
            "Database flag 'google_ml_integration.enable_model_support' must be 'on'."
        )

    ai_query_engine_value = await connection_manager.fetch_val(
        "SELECT setting FROM pg_settings "
        "WHERE name = 'google_ml_integration.enable_ai_query_engine'"
    )
    ai_query_engine_enabled = ai_query_engine_value == "on"
    if config.require_ai_query_engine and not ai_query_engine_enabled:
        errors.append(
            "Database flag 'google_ml_integration.enable_ai_query_engine' must be 'on'."
        )

    try:
        default_model_available = bool(
            await connection_manager.fetch_val(
                "SELECT 1 FROM google_ml.model_info_view WHERE model_id = :model_id LIMIT 1",
                {"model_id": config.default_embedding_model},
            )
        )
    except Exception as exc:
        raise AlloyNativeModelError(
            "Model availability validation failed while querying google_ml.model_info_view."
        ) from exc

    if not default_model_available:
        errors.append(
            f"Default embedding model '{config.default_embedding_model}' is not available."
        )

    if errors:
        combined = "\n".join(f"- {item}" for item in errors)
        raise AlloyNativeValidationError(
            "Environment validation failed:\n" + combined
        )

    return ValidationReport(
        google_ml_extension_version=str(google_ml_extension_version),
        vector_extension_version=str(vector_extension_version),
        model_support_enabled=model_support_enabled,
        ai_query_engine_enabled=ai_query_engine_enabled,
        default_embedding_model_available=default_model_available,
    )
