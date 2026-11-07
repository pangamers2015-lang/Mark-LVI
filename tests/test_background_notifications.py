"""Tests for safe, provider-agnostic background task announcements."""
import unittest

from core.background_notifications import build_task_notification


class BackgroundNotificationTests(unittest.TestCase):
    def test_completed_fcc_result_hides_provider_metadata(self):
        prompt = build_task_notification({
            "id": "BG-0001",
            "name": "fcc_cloud",
            "summary": "Pesquisar o resultado do último jogo do Flamengo",
            "status": "completed",
            "result": (
                "FCC Cloud completed the task.\n"
                "Working directory: C:\\Yon\\project\n"
                "Session ID: private-session\n"
                "Reported API cost: US$ 0.05\n"
                "Result:\nFlamengo venceu por 2 a 1."
            ),
        })
        self.assertIn("Flamengo venceu por 2 a 1.", prompt)
        self.assertNotIn("private-session", prompt)
        self.assertNotIn("C:\\Yon", prompt)
        self.assertNotIn("US$ 0.05", prompt)
        self.assertNotIn("FCC Cloud", prompt)

    def test_failed_task_is_reported_as_failure(self):
        prompt = build_task_notification({
            "id": "BG-0002",
            "name": "fcc_cloud",
            "summary": "Executar uma tarefa",
            "status": "failed",
            "result": "Timeout after 900 seconds.",
        })
        self.assertIn("terminou com uma falha", prompt)
        self.assertIn("Timeout after 900 seconds.", prompt)

    def test_notification_does_not_expose_internal_task_id(self):
        prompt = build_task_notification({
            "id": "BG-0099",
            "name": "web_search",
            "summary": "Pesquisar uma informação",
            "status": "completed",
            "result": "Informação confirmada.",
        })
        self.assertNotIn("BG-0099", prompt)
        self.assertIn("Informação confirmada.", prompt)


if __name__ == "__main__":
    unittest.main()
