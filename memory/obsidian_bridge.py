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
        memories = cognitive_store.list_memories(limit=1000)
        goals = cognitive_store.list_goals(include_finished=True, limit=100)
        from memory import cognitive_runtime
        relations = cognitive_runtime.list_memory_relations(limit=10000)
        by_id = {int(item["id"]): item for item in memories}
        linked = {memory_id: [] for memory_id in by_id}
        for edge in relations:
            source, target_id = int(edge["source_id"]), int(edge["target_id"])
            if source in by_id and target_id in by_id:
                linked[source].append((target_id, edge["relation"]))
        target = vault / "Yon" / "Generated"
        target.mkdir(parents=True, exist_ok=True)
        memory_lines = [
            "# Yon — Generated Cognitive Memories", "",
            f"> Generated from Yon's local SQLite database at {now}. SQLite remains authoritative.", "",
        ]
        for item in reversed(memories):
            mid = int(item["id"])
            links = linked.get(mid, [])
            note_name = f"Memory {mid}.generated"
            memory_lines.extend([
                f"## [[{note_name}|Memory {mid}]] — {item['level']}",
                f"- State: {item['state']}", f"- Source: {item['source']}",
                f"- Created: {item['created_at']}",
                f"- Evidence: {item['evidence'] or 'Not recorded'}",
                f"- Related memories: {len(links)}", "", item["content"], "",
            ])
            note_lines = [
                f"# Memory {mid}", "",
                f"- Level: {item['level']}", f"- State: {item['state']}",
                f"- Source: {item['source']}", f"- Created: {item['created_at']}",
                f"- Validated: {item['validated_at'] or 'Not validated'}",
                f"- Evidence: {item['evidence'] or 'Not recorded'}", "",
                item["content"], "", "## Connections",
            ]
            if links:
                note_lines.extend(
                    f"- [[Memory {other}.generated]] — {relation}"
                    for other, relation in sorted(links)
                )
            else:
                note_lines.append("- No connections recorded yet.")
            _atomic_write(target / f"Memory {mid}.generated.md", "\n".join(note_lines) + "\n")
        graph_lines = [
            "# Yon — Knowledge Graph", "",
            f"> Automatically generated at {now}. Tentative links are suggestions, not verified equivalences.", "",
            f"- Memories in this export: {len(memories)}",
            f"- Relationships in this export: {sum(len(v) for v in linked.values())}", "",
            "## Memory nodes",
        ]
        graph_lines.extend(
            f"- [[Memory {mid}.generated]] — {item['content'][:140].replace(chr(10), ' ')}"
            for mid, item in sorted(by_id.items())
        )
        graph_lines.extend(["", "## Relationships"])
        for edge in relations:
            source, target_id = int(edge["source_id"]), int(edge["target_id"])
            if source in by_id and target_id in by_id:
                graph_lines.append(
                    f"- [[Memory {source}.generated]] — {edge['relation']} → [[Memory {target_id}.generated]]"
                )
        _atomic_write(target / "Memory Graph.generated.md", "\n".join(graph_lines) + "\n")
        goal_lines = [
            "# Yon — Generated Objectives", "",
            f"> Generated from Yon's local SQLite database at {now}. SQLite remains authoritative.", "",
        ]
        for goal in goals:
            goal_lines.extend([
                f"## {goal['title']} (#{goal['id']})", f"- Status: {goal['status']}",
                f"- Priority: {goal['priority']}", f"- Updated: {goal['updated_at']}", "",
                goal["description"] or "No description recorded.", "",
            ])
        _atomic_write(target / "Cognitive Memories.generated.md", "\n".join(memory_lines) + "\n")
        _atomic_write(target / "Objectives.generated.md", "\n".join(goal_lines) + "\n")
        return {"ok": True, "files": [str(target / "Memory Graph.generated.md"),
                str(target / "Cognitive Memories.generated.md"), str(target / "Objectives.generated.md")],
                "memory_count": len(memories), "goal_count": len(goals),
                "relationship_count": sum(len(v) for v in linked.values())}
    except OSError as exc:
        return {"ok": False, "error": f"Could not export notes: {exc}"}
