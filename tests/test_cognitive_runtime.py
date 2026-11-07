"""Isolated tests for the Yon cognitive runtime; never touch the user's real databases."""
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from memory import cognitive_store
from memory import cognitive_runtime


class CognitiveRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"YON_OBSIDIAN_VAULT": ""})
        self.env_patch.start()
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
        self.env_patch.stop()

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

    def test_new_memories_get_conservative_automatic_graph_links(self):
        first = cognitive_runtime.remember(
            "DuckDuckGo pesquisa páginas da internet e retorna fontes para pesquisa.",
            source="unit_test", state="hypothesis"
        )
        second = cognitive_runtime.remember(
            "Usar DuckDuckGo para pesquisar páginas da internet e encontrar fontes confiáveis.",
            source="unit_test", state="hypothesis"
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        edges = cognitive_runtime.list_memory_relations()
        self.assertTrue(any(
            edge["source_id"] == second and edge["target_id"] == first
            and edge["relation"] == "possible_related_to"
            and "lexical" in edge["evidence"]
            for edge in edges
        ))

    def test_obsidian_export_builds_linked_graph_notes(self):
        from memory.obsidian_bridge import export_cognitive_notes
        first = cognitive_runtime.remember(
            "Pesquisa na internet encontra páginas e fontes confiáveis.",
            source="unit_test", state="hypothesis"
        )
        second = cognitive_runtime.remember(
            "Pesquisar páginas na internet e verificar fontes confiáveis.",
            source="unit_test", state="hypothesis"
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        vault = Path(self.temp.name) / "vault"
        vault.mkdir()
        with patch.dict(os.environ, {"YON_OBSIDIAN_VAULT": str(vault)}):
            result = export_cognitive_notes()
        self.assertTrue(result["ok"], result)
        graph_file = vault / "Yon" / "Generated" / "Memory Graph.generated.md"
        note_file = vault / "Yon" / "Generated" / f"Memory {second}.generated.md"
        self.assertTrue(graph_file.exists())
        self.assertTrue(note_file.exists())
        self.assertIn(f"[[Memory {first}.generated]]", note_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
