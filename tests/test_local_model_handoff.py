"""Focused tests for the Ollama bridge and Yon local-model handoff."""
import json
import unittest
from unittest.mock import Mock, patch

from core.cognitive_models import ollama_chat
from actions.yon_brain import yon_brain


class OllamaBridgeTests(unittest.TestCase):
    @patch("core.cognitive_models.urlopen")
    def test_compact_profile_disables_thinking_and_returns_visible_content(self, urlopen):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "message": {"content": "QWEN INTEGRADO COM SUCESSO"},
            "done_reason": "stop",
        }).encode("utf-8")
        urlopen.return_value = response

        result = ollama_chat("Responda somente: QWEN INTEGRADO COM SUCESSO")

        self.assertTrue(result["ok"])
        self.assertEqual(result["response"], "QWEN INTEGRADO COM SUCESSO")
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertFalse(payload["think"])
        self.assertEqual(payload["messages"][-1]["content"],
                         "Responda somente: QWEN INTEGRADO COM SUCESSO")

    @patch("core.cognitive_models.urlopen")
    def test_empty_visible_content_is_reported_as_failure(self, urlopen):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "message": {"content": "", "thinking": "private reasoning"},
            "done_reason": "length",
        }).encode("utf-8")
        urlopen.return_value = response

        result = ollama_chat("Responda somente: teste")

        self.assertFalse(result["ok"])
        self.assertIn("no visible answer", result["error"].lower())


class YonLocalHandoffTests(unittest.TestCase):
    @patch("core.cognitive_models.ollama_chat")
    @patch("actions.yon_brain.brain.build_context",
           side_effect=AssertionError("full conversation context must not be injected"))
    def test_consult_local_passes_focused_assignment_and_returns_qwen_text(
        self, build_context, ollama
    ):
        ollama.return_value = {
            "ok": True,
            "model": "qwen3.5:4b",
            "response": "QWEN INTEGRADO COM SUCESSO",
        }

        result = yon_brain({
            "action": "consult_local",
            "prompt": "Responda somente: QWEN INTEGRADO COM SUCESSO",
        })

        self.assertIn("QWEN INTEGRADO COM SUCESSO", result)
        build_context.assert_not_called()
        sent_prompt = ollama.call_args.args[0]
        self.assertEqual(sent_prompt,
                         "Responda somente: QWEN INTEGRADO COM SUCESSO")
        self.assertEqual(ollama.call_args.kwargs["profile"], "compact")

    @patch("core.cognitive_models.ollama_chat")
    @patch("actions.yon_brain.brain.retrieve")
    def test_memory_context_is_opt_in_and_limited(self, retrieve, ollama):
        retrieve.return_value = [{
            "level": "semantic",
            "state": "confirmed",
            "content": "Relevant saved project fact.",
        }]
        ollama.return_value = {
            "ok": True, "model": "qwen3.5:4b", "response": "Analysis complete."
        }

        yon_brain({
            "action": "consult_local",
            "prompt": "Analyze the saved project fact.",
            "use_memory_context": True,
        })

        retrieve.assert_called_once_with(
            "Analyze the saved project fact.", limit=3, semantic=False
        )
        self.assertIn("Relevant saved project fact.", ollama.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
