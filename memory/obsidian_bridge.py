"""Optional Markdown export bridge for Obsidian.

SQLite remains the source of truth. This module only writes generated read-only views
inside a configured vault; it never reads or depends on Obsidian's internal database.
"""
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timezone
from memory import cognitive_store


def _vault_path(vault_path=None):
    raw = str(vault_path or os.environ.get("YON_OBSIDIAN_VAULT", "")).strip()
    return Path(raw).expanduser() if raw else None


def _atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".yon-tmp")
    try:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def export_cognitive_notes(vault_path=None) -> dict:
    vault = _vault_path(vault_path)
    if vault is None:
        return {"ok": False, "error": "Configure YON_OBSIDIAN_VAULT with the full path to the Obsidian vault."}
    try:
        if not vault.exists() or not vault.is_dir():
            return {"ok": False, "error": f"Obsidian vault directory does not exist: {vault}"}
        now = datetime.now(timezone.utc).isoformat(timespec="minutes")
        memories = cognitive_store.search_memories("", limit=30)
        goals = cognitive_store.list_goals(include_finished=True, limit=100)
        memory_lines = [
            "# Yon — Generated Cognitive Memories",
            "",
            f"> Generated from Yon's local SQLite database at {now}. SQLite remains authoritative.",
            "",
        ]
        for item in memories:
            memory_lines.extend([
                f"## Memory {item['id']} — {item['level']}",
                f"- State: {item['state']}",
                f"- Source: {item['source']}",
                f"- Created: {item['created_at']}",
                f"- Evidence: {item['evidence'] or 'Not recorded'}",
                "",
                item["content"],
                "",
            ])
        goal_lines = [
            "# Yon — Generated Objectives",
            "",
            f"> Generated from Yon's local SQLite database at {now}. SQLite remains authoritative.",
            "",
        ]
        for goal in goals:
            goal_lines.extend([
                f"## {goal['title']} (#{goal['id']})",
                f"- Status: {goal['status']}",
                f"- Priority: {goal['priority']}",
                f"- Updated: {goal['updated_at']}",
                "",
                goal["description"] or "No description recorded.",
                "",
            ])
        target = vault / "Yon" / "Generated"
        memory_file = target / "Cognitive Memories.generated.md"
        goals_file = target / "Objectives.generated.md"
        _atomic_write(memory_file, "\n".join(memory_lines))
        _atomic_write(goals_file, "\n".join(goal_lines))
        return {"ok": True, "files": [str(memory_file), str(goals_file)],
                "memory_count": len(memories), "goal_count": len(goals)}
    except OSError as exc:
        return {"ok": False, "error": f"Could not export notes: {exc}"}
