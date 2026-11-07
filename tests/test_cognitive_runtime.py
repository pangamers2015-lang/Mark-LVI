"""Isolated tests for the Yon cognitive runtime; never touch the user's real databases."""
import tempfile
import unittest
from pathlib import Path

from memory import cognitive_store
from memory import cognitive_runtime


class CognitiveRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old_store_path = cognitive_store.DB_PATH
        self.old_runtime_path = cognitive_runtime._DB
        cognitive_store.DB_PATH = root / "test_cognitive.sqlite3"
        cognitive_runtime._DB = cognitive_store.DB_PATH
        cognitive_runtime._EMBEDDER = None
        cognitive_runtime._EMBEDDER_ERROR = "disabled in isolated unit test"
        self.assertTrue(cognitive_runtime.initialize())

    def tearDown(self):
        cognitive_store.DB_PATH = self.old_store_path
        cognitive_runtime._DB = self.old_runtime_path
        cognitive_runtime._EMBEDDER = None
        cognitive_runtime._EMBEDDER_ERROR = ""
        self.temp.cleanup()

    def test_memory_provenance_and_fts_retrieval(self):
        memory_id = cognitive_runtime.remember(
            "The Yon project keeps voice and interface systems intact.",
            level="semantic", source="unit_test", state="confirmed",
            evidence="Explicit isolated unit-test fixture.",
        )
        self.assertIsNotNone(memory_id)
        results = cognitive_runtime.retrieve("voice interface", semantic=False)
        self.assertTrue(any(item["id"] == memory_id for item in results))

    def test_confirmed_memory_requires_evidence(self):
        self.assertIsNone(cognitive_runtime.remember(
            "A claim without supporting evidence.", state="confirmed"
        ))

    def test_goal_dependencies_reject_cycles(self):
        first = cognitive_store.save_goal("First objective", priority=1)
        second = cognitive_store.save_goal("Second objective", priority=2)
        self.assertTrue(cognitive_runtime.add_goal_dependency(first, second))
        self.assertFalse(cognitive_runtime.add_goal_dependency(second, first))

    def test_consolidation_requires_confirmed_memory_and_evidence(self):
        mid = cognitive_runtime.remember(
            "A repeatable verified procedure.", state="confirmed",
            evidence="The procedure passed the documented validation."
        )
        self.assertFalse(cognitive_runtime.consolidate_memory(mid, ""))
        self.assertTrue(cognitive_runtime.consolidate_memory(
            mid, "Repeated validation recorded by isolated test."
        ))

    def test_supervisor_returns_assessment_plan_and_review(self):
        result = cognitive_runtime.run_cognitive_cycle(
            "Implement a multi-step project and verify the final result."
        )
        self.assertTrue(result["assessment"]["multi_step"])
        self.assertTrue(result["plan"])
        self.assertIn("not been verified", result["review"])


if __name__ == "__main__":
    unittest.main()
