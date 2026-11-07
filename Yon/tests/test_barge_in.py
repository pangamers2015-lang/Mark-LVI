import unittest

from barge_in import BargeInDetector


class BargeInDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = BargeInDetector()

    def test_requires_sustained_confirmed_speech(self):
        self.assertIsNone(self.detector.observe(b"a", True, 3))
        self.assertIsNone(self.detector.observe(b"b", True, 3))
        self.assertEqual(self.detector.observe(b"c", True, 3), [b"a", b"b", b"c"])

    def test_noise_resets_pending_speech(self):
        self.assertIsNone(self.detector.observe(b"a", True, 2))
        self.assertIsNone(self.detector.observe(b"noise", False, 2))
        self.assertIsNone(self.detector.observe(b"b", True, 2))
        self.assertEqual(self.detector.observe(b"c", True, 2), [b"b", b"c"])

    def test_requires_at_least_one_block(self):
        self.assertEqual(self.detector.observe(b"voice", True, 0), [b"voice"])

    def test_reset_discards_partial_capture(self):
        self.assertIsNone(self.detector.observe(b"a", True, 2))
        self.detector.reset()
        self.assertIsNone(self.detector.observe(b"b", True, 2))


if __name__ == "__main__":
    unittest.main()
