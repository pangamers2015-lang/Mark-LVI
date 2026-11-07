"""Tests for safe, provider-agnostic background task announcements."""
import unittest

from core.background_notifications import build_task_notification, can_deliver_notification


class BackgroundNotificationTests(unittest.TestCase):
    def test_delivery_waits_until_speech_and_audio_are_idle(self):
        base = {
            "turn_complete_at": 10.0,
            "now": 12.0,
            "speaking": False,
            "audio_pending": False,
            "tail_active": False,
            "user_quiet_for": 2.0,
        }
        self.assertTrue(can_deliver_notification(**base))
        self.assertFalse(can_deliver_notification(**{**base, "speaking": True}))
        self.assertFalse(can_deliver_notification(**{**base, "audio_pending": True}))
        self.assertFalse(can_deliver_notification(**{**base, "tail_active": True}))
        self.assertFalse(can_deliver_notification(**{**base, "now": 11.0}))
        self.assertFalse(can_deliver_notification(**{**base, "user_quiet_for": 0.2}))

    def test_wake_word_sleep_blocks_announcement(self):
        self.assertFalse(can_deliver_notification(
            turn_complete_at=10.0, now=12.0, speaking=False,
            audio_pending=False, tail_active=False, user_quiet_for=2.0,
            wake_enabled=True, awake=False,
        ))

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

    def test_escaped_fcc_separator_is_supported(self):
        prompt = build_task_notification({
            "id": "BG-0003",
            "name": "fcc_cloud",
            "summary": "Pesquisar uma informação",
            "status": "completed",
            "result": (
                "FCC Cloud completed the task.\\n"
                "Working directory: C:\\Yon\\project\\n"
                "Session ID: private-session\\n"
                "Result:\\nResultado confirmado."
            ),
        })
        self.assertIn("Resultado confirmado.", prompt)
        self.assertNotIn("private-session", prompt)
        self.assertNotIn("Working directory", prompt)

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
