import unittest
from unittest.mock import Mock, patch

import requests

from actions.research_engine import _dedupe, _format_sources, _route, _siftdog_search


class ResearchEngineUnitTests(unittest.TestCase):
    def test_router_sends_deep_state_to_planner(self):
        self.assertEqual(_route({"depth": "deep"}), "deep_plan")

    def test_router_sends_shallow_state_to_fast_research(self):
        self.assertEqual(_route({"depth": "shallow"}), "shallow")

    def test_auto_mode_selects_deep_for_complex_research_request(self):
        from actions.research_engine import _orchestrate
        state = _orchestrate({
            "query": "Investigue profundamente e compare as causas e consequências",
            "mode": "auto",
        })
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

    @patch("actions.research_engine._keys", return_value={})
    @patch("actions.research_engine.requests.post")
    def test_siftdog_search_uses_local_api_without_paid_key(self, post, _keys):
        response = Mock()
        response.json.return_value = {
            "results": [{
                "title": "Example",
                "url": "https://example.com",
                "content": "Snippet",
                "raw_content": "Full text",
                "score": 0.9,
            }]
        }
        response.raise_for_status.return_value = None
        post.return_value = response

        rows = _siftdog_search("test query", deep=True, limit=3)

        self.assertEqual(rows[0]["title"], "Example")
        self.assertEqual(rows[0]["raw_content"], "Full text")
        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:8000/search")
        self.assertEqual(post.call_args.kwargs["json"]["search_depth"], "advanced")
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])

    @patch("actions.research_engine._keys", return_value={})
    @patch("actions.research_engine.requests.post", side_effect=requests.ConnectionError("offline"))
    def test_siftdog_unavailable_returns_actionable_error(self, _post, _keys):
        with self.assertRaisesRegex(RuntimeError, "scripts/start_siftdog.ps1"):
            _siftdog_search("test query")


if __name__ == "__main__":
    unittest.main()
