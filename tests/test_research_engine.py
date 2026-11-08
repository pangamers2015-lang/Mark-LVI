import unittest
from actions.research_engine import _dedupe, _format_sources, _route


class ResearchEngineUnitTests(unittest.TestCase):
    def test_router_sends_deep_state_to_planner(self):
        self.assertEqual(_route({"depth": "deep"}), "deep_plan")

    def test_router_sends_shallow_state_to_fast_research(self):
        self.assertEqual(_route({"depth": "shallow"}), "shallow")

    def test_auto_mode_selects_deep_for_complex_research_request(self):
        from actions.research_engine import _orchestrate
        state = _orchestrate({"query": "Investigue profundamente e compare as causas e consequências", "mode": "auto"})
        self.assertEqual(state["depth"], "deep")

    def test_dedupe_keeps_first_result_per_url(self):
        rows = [
            {"title": "First", "url": "https://example.com/a"},
            {"title": "Duplicate", "url": "https://example.com/a"},
            {"title": "Second", "url": "https://example.com/b"},
        ]
        self.assertEqual([x["title"] for x in _dedupe(rows)], ["First", "Second"])

    def test_source_formatter_preserves_numbered_urls(self):
        rendered = _format_sources([
            {"title": "Primary source", "url": "https://example.com", "content": "Evidence"}
        ])
        self.assertIn("[1] Primary source", rendered)
        self.assertIn("URL: https://example.com", rendered)
        self.assertIn("EVIDÊNCIA: Evidence", rendered)


if __name__ == "__main__":
    unittest.main()
