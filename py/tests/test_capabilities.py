"""Tests for capability detection helpers."""

from unittest import TestCase

from alloynative.capabilities import CapabilitySnapshot


class CapabilitySnapshotTest(TestCase):
    """Ensure extension snapshots map to the right runtime capabilities."""

    def test_from_extensions_detects_pgvector_only(self) -> None:
        snapshot = CapabilitySnapshot.from_extensions({"vector"})

        self.assertTrue(snapshot.has_pgvector)
        self.assertFalse(snapshot.has_scann)
        self.assertEqual(snapshot.preferred_index_type, "ivfflat")

    def test_from_extensions_detects_scann_when_present(self) -> None:
        snapshot = CapabilitySnapshot.from_extensions({"vector", "alloydb_scann"})

        self.assertTrue(snapshot.has_pgvector)
        self.assertTrue(snapshot.has_scann)
        self.assertEqual(snapshot.preferred_index_type, "scann")

    def test_from_extensions_handles_missing_extensions(self) -> None:
        snapshot = CapabilitySnapshot.from_extensions(set())

        self.assertFalse(snapshot.has_pgvector)
        self.assertFalse(snapshot.has_scann)
        self.assertEqual(snapshot.preferred_index_type, "ivfflat")
