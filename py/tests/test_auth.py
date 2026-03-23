"""Tests for AlloyNative IAM auth helpers."""

from types import SimpleNamespace
from unittest import TestCase

from alloynative.auth import extract_principal_email, resolve_db_user


class AuthHelpersTest(TestCase):
    """Keep the auth layer deterministic without requiring live GCP credentials."""

    def test_extract_principal_email_from_service_account_credentials(self) -> None:
        credentials = SimpleNamespace(
            service_account_email="svc@example.iam.gserviceaccount.com"
        )
        self.assertEqual(
            extract_principal_email(credentials),
            "svc@example.iam.gserviceaccount.com",
        )

    def test_resolve_db_user_prefers_explicit_value(self) -> None:
        self.assertEqual(resolve_db_user("user@example.com"), "user@example.com")
