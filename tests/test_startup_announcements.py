import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import startup_announcements as announcements


class StartupAnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(
            announcements, "ANNOUNCEMENTS_PATH",
            Path(self.temp.name) / "startup_announcements.json",
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp.cleanup()

    def test_siftdog_notice_is_pending_only_until_delivered(self):
        first = announcements.pending_announcements()
        self.assertEqual(
            [item["id"] for item in first],
            ["siftdog-native-research-2026-11-07"],
        )
        self.assertEqual(
            announcements.mark_announcements_delivered([first[0]["id"]]), 1
        )
        self.assertEqual(announcements.pending_announcements(), [])

    def test_new_capability_notice_is_persistent_and_deduplicated(self):
        self.assertTrue(announcements.register_announcement(
            "capability-x", "Capability X", "Capability X is now available."
        ))
        self.assertFalse(announcements.register_announcement(
            "capability-x", "Capability X", "Duplicate notice."
        ))
        pending = announcements.pending_announcements()
        ids = {item["id"] for item in pending}
        self.assertIn("capability-x", ids)
        self.assertIn("siftdog-native-research-2026-11-07", ids)


if __name__ == "__main__":
    unittest.main()
