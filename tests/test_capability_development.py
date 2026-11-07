"""Isolated tests for supervised capability proposals and rejection filters."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions import capability_development as lab


class CapabilityDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old_db, self.old_root = lab.DB_PATH, lab.LAB_ROOT
        lab.DB_PATH = root / "memory" / "capabilities.sqlite3"
        lab.LAB_ROOT = root / ".yon_capability_lab"

    def tearDown(self):
        lab.DB_PATH, lab.LAB_ROOT = self.old_db, self.old_root
        self.temp.cleanup()

    def call_tool(self, **params):
        return lab.capability_development({"action": params.pop("action"), **params})

    def create_proposal(self):
        result = self.call_tool(
            action="propose", title="Windows folder access",
            topic="Access folders on Windows",
            limitation="Yon has no suitable folder browsing action.",
            approach="Use Python pathlib and a restricted local file access tool.",
            cloud_findings="Use pathlib with explicit allowed roots.",
            implementation_plan="Create a small read-only folder listing action.",
            risks="Path traversal and privacy exposure.",
            dependencies="Python standard library only.",
            test_plan="Test allowed paths, blocked paths and missing folders."
        )
        self.assertIn("UPDATE NOTE", result)
        self.assertIn("No files have been installed", result)
        return 1

    def test_proposal_waits_for_approval_and_creates_no_workspace(self):
        self.create_proposal()
        self.assertFalse(lab.LAB_ROOT.exists())

    def test_approval_creates_isolated_workspace(self):
        proposal_id = self.create_proposal()
        result = self.call_tool(action="approve", proposal_id=proposal_id)
        self.assertIn("Sandbox approved", result)
        workspace = lab.LAB_ROOT / "workspaces" / "proposal-000001"
        self.assertTrue((workspace / "README.md").exists())
        self.assertIn("Do not edit the Yon production source tree",
                        (workspace / "README.md").read_text(encoding="utf-8"))

    def test_rejection_erases_details_but_keeps_narrow_filter(self):
        proposal_id = self.create_proposal()
        result = self.call_tool(action="reject", proposal_id=proposal_id,
                                reason="This implementation is not relevant.")
        self.assertIn("implementation details were erased", result)
        fetched = self.call_tool(action="get", proposal_id=proposal_id)
        self.assertNotIn("Use pathlib with explicit allowed roots", fetched)
        blocked = self.call_tool(
            action="propose", title="Same folder tool",
            topic="Access folders on Windows",
            limitation="Same missing capability.",
            approach="Use Python pathlib and a restricted local file access tool."
        )
        self.assertIn("previously rejected", blocked)

    def test_sandbox_pass_requires_evidence_and_separate_integration_approval(self):
        proposal_id = self.create_proposal()
        self.call_tool(action="approve", proposal_id=proposal_id)
        missing = self.call_tool(
            action="record_result", proposal_id=proposal_id,
            result_status="sandbox_passed", result_summary="Tests passed."
        )
        self.assertIn("Evidence is required", missing)
        passed = self.call_tool(
            action="record_result", proposal_id=proposal_id,
            result_status="sandbox_passed", result_summary="Isolated tests passed.",
            test_evidence="pytest: 4 passed; tested only inside sandbox."
        )
        self.assertIn("separate approval", passed)
        approved = self.call_tool(action="approve_integration", proposal_id=proposal_id)
        self.assertIn("Integration approved", approved)


if __name__ == "__main__":
    unittest.main()
