import unittest
from pathlib import Path

from core.action_loader import discover_actions


class CognitiveActionDiscoveryTests(unittest.TestCase):
    def test_yon_brain_is_discovered_and_declared(self):
        root = Path(__file__).resolve().parents[1]
        logs = []
        registry = discover_actions(root / "actions", logger=logs.append)

        self.assertTrue(registry.has("yon_brain"), msg="\n".join(logs))
        declarations = registry.get_tool_declarations()
        brain_declaration = next(
            (item for item in declarations if item.get("name") == "yon_brain"),
            None,
        )
        self.assertIsNotNone(brain_declaration)
        self.assertIn("reflect", brain_declaration["parameters"]["properties"]["action"]["enum"])


if __name__ == "__main__":
    unittest.main()
