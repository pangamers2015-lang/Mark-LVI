import unittest
from pathlib import Path

from web_ui import _safe_drop_relative_path


class SafeDropPathTests(unittest.TestCase):
    def test_keeps_nested_relative_path(self):
        self.assertEqual(
            _safe_drop_relative_path("Projeto/subpasta/arquivo.txt"),
            Path("Projeto") / "subpasta" / "arquivo.txt",
        )

    def test_normalizes_windows_separators(self):
        self.assertEqual(
            _safe_drop_relative_path(r"Projeto\\subpasta\\arquivo.txt"),
            Path("Projeto") / "subpasta" / "arquivo.txt",
        )

    def test_rejects_parent_traversal(self):
        self.assertIsNone(_safe_drop_relative_path("../segredo.txt"))
        self.assertIsNone(_safe_drop_relative_path("Projeto/../../segredo.txt"))

    def test_rejects_absolute_and_drive_paths(self):
        self.assertIsNone(_safe_drop_relative_path("/etc/passwd"))
        self.assertIsNone(_safe_drop_relative_path(r"C:\\Users\\arquivo.txt"))

    def test_rejects_empty_names(self):
        self.assertIsNone(_safe_drop_relative_path(""))
        self.assertIsNone(_safe_drop_relative_path("."))


if __name__ == "__main__":
    unittest.main()
