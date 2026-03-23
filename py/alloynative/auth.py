"""Helpers for resolving the IAM principal used as the AlloyDB DB user."""

from __future__ import annotations

import re
from typing import Any

from .errors import AlloyNativeAuthError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_db_user(db_user: str) -> str:
    """Normalize a user-supplied DB user and validate basic email shape."""

    value = db_user.strip()
    if not value:
        raise AlloyNativeAuthError("DB user cannot be empty.")
    if "@" not in value:
        raise AlloyNativeAuthError(
            "DB user must be an email address for IAM-authenticated AlloyDB access."
        )
    return value


def extract_principal_email(credentials: Any) -> str | None:
    """Extract an email-like principal from a credential object if possible."""

    for attribute in (
        "service_account_email",
        "_service_account_email",
        "signer_email",
    ):
        value = getattr(credentials, attribute, None)
        if isinstance(value, str) and _EMAIL_RE.match(value.strip()):
            return value.strip()
    return None


def resolve_db_user(explicit_db_user: str | None = None) -> str:
    """Resolve the AlloyDB DB user, preferring an explicit user when provided."""

    if explicit_db_user:
        return normalize_db_user(explicit_db_user)

    try:
        import google.auth  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - import path depends on env
        raise AlloyNativeAuthError(
            "google-auth is required to auto-discover the IAM DB user. "
            "Install google-auth or pass db_user explicitly."
        ) from exc

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/userinfo.email"]
        )
    except Exception as exc:  # pragma: no cover - requires live credentials
        raise AlloyNativeAuthError(
            "Unable to discover application default credentials for AlloyDB IAM auth."
        ) from exc

    email = extract_principal_email(credentials)
    if email:
        return normalize_db_user(email)

    raise AlloyNativeAuthError(
        "Could not derive an IAM principal email from the active credentials. "
        "Pass db_user explicitly."
    )
