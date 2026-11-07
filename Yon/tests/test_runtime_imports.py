import unittest


class RuntimeImportTests(unittest.TestCase):
    def test_application_modules_import(self):
        import app  # noqa: F401
        import barge_in  # noqa: F401
        import echo_guard  # noqa: F401
        import voice_live  # noqa: F401


if __name__ == "__main__":
    unittest.main()
