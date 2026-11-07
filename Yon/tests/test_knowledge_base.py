import unittest

from knowledge_base import load_system_context


class KnowledgeBaseTests(unittest.TestCase):
    def test_system_context_loads_technical_reference(self):
        context = load_system_context()
        self.assertIn("Você é Yon", context)
        self.assertIn("Godot", context)
        self.assertIn("Phaser", context)
        self.assertIn("critérios de aceitação", context.lower())

    def test_system_context_sets_execution_boundaries(self):
        context = load_system_context()
        self.assertIn("sem evidência", context)
        self.assertIn("integradas e autorizadas", context)


if __name__ == "__main__":
    unittest.main()
