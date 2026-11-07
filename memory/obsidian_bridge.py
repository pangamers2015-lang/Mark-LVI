"""Structured, read-only Obsidian views generated from Yon's SQLite memory.

SQLite remains the source of truth. Existing root-level generated note names are
preserved for backward-compatible wikilinks; navigational indexes live in
Yon/Generated/Indexes and never become runtime dependencies.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

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


def _tag(value):
    value = re.sub(r"[^a-zA-Z0-9_/-]+", "-", str(value or "unknown").strip().lower())
    return value.strip("-") or "unknown"


def _group_index(title, field, groups, now):
    lines = [
        f"# {title}", "",
        f"> Generated from local SQLite at {now}. This is a navigation index, not a separate memory store.", "",
    ]
    if not groups:
        lines.append("_No entries yet._")
    for key in sorted(groups):
        items = groups[key]
        lines.extend([f"## {key} ({len(items)})", ""])
        for item in items:
            mid = int(item["id"])
            preview = str(item["content"]).replace("\n", " ").strip()[:180]
            lines.append(f"- [[Memory {mid}.generated|Memory {mid}]] — {preview}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_cognitive_notes(vault_path=None) -> dict:
    vault = _vault_path(vault_path)
    if vault is None:
        return {"ok": False, "error": "Configure YON_OBSIDIAN_VAULT with the full path to the Obsidian vault."}
    try:
        if not vault.exists() or not vault.is_dir():
            return {"ok": False, "error": "Configured Obsidian vault directory does not exist."}

        now = datetime.now(timezone.utc).isoformat(timespec="minutes")
        memories = cognitive_store.list_memories(limit=2000)
        goals = cognitive_store.list_goals(include_finished=True, limit=100)
        from memory import cognitive_runtime
        relations = cognitive_runtime.list_memory_relations(limit=10000)

        by_id = {int(item["id"]): item for item in memories}
        linked = defaultdict(list)
        for edge in relations:
            source, target_id = int(edge["source_id"]), int(edge["target_id"])
            if source in by_id and target_id in by_id:
                linked[source].append((target_id, edge["relation"]))

        target = vault / "Yon" / "Generated"
        indexes = target / "Indexes"
        target.mkdir(parents=True, exist_ok=True)
        indexes.mkdir(parents=True, exist_ok=True)

        # Preserve existing note filenames so current Obsidian wikilinks do not break.
        memory_lines = [
            "# Yon — Cognitive Memories", "",
            f"> Generated from local SQLite at {now}. SQLite remains authoritative.", "",
            "Use [[Home.generated]] for navigation and the Indexes folder for grouped views.", "",
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
                "---",
                f"yon_memory_id: {mid}",
                f"level: {_tag(item['level'])}",
                f"state: {_tag(item['state'])}",
                f"source: {_tag(item['source'])}",
                f"tags: [yon/memory, yon/level/{_tag(item['level'])}, yon/state/{_tag(item['state'])}]",
                "---", "",
                f"# Memory {mid}", "",
                f"- **Level:** {item['level']}",
                f"- **State:** {item['state']}",
                f"- **Source:** {item['source']}",
                f"- **Created:** {item['created_at']}",
                f"- **Validated:** {item['validated_at'] or 'Not validated'}",
                f"- **Evidence:** {item['evidence'] or 'Not recorded'}", "",
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

        # Grouped navigation views: level, evidence state and origin.
        groups_by_level = defaultdict(list)
        groups_by_state = defaultdict(list)
        groups_by_source = defaultdict(list)
        for item in memories:
            groups_by_level[str(item["level"])].append(item)
            groups_by_state[str(item["state"])].append(item)
            groups_by_source[str(item["source"])].append(item)

        _atomic_write(indexes / "By Level.generated.md",
                      _group_index("Memories by Level", "level", groups_by_level, now))
        _atomic_write(indexes / "By Evidence State.generated.md",
                      _group_index("Memories by Evidence State", "state", groups_by_state, now))
        _atomic_write(indexes / "By Source.generated.md",
                      _group_index("Memories by Source", "source", groups_by_source, now))

        graph_lines = [
            "# Yon — Knowledge Graph", "",
            f"> Generated at {now}. Suggested links are not verified equivalences.", "",
            f"- Memories: {len(memories)}",
            f"- Relationships: {sum(len(v) for v in linked.values())}", "",
            "## Memory nodes",
        ]
        graph_lines.extend(
            f"- [[Memory {mid}.generated]] — {str(item['content']).replace(chr(10), ' ')[:140]}"
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
            "# Yon — Objectives", "",
            f"> Generated from local SQLite at {now}. SQLite remains authoritative.", "",
        ]
        goals_by_status = defaultdict(list)
        for goal in goals:
            goals_by_status[str(goal["status"])].append(goal)
            goal_lines.extend([
                f"## {goal['title']} (#{goal['id']})",
                f"- Status: {goal['status']}", f"- Priority: {goal['priority']}",
                f"- Updated: {goal['updated_at']}", "",
                goal["description"] or "No description recorded.", "",
            ])
        goal_index = [
            "# Objectives by Status", "",
            f"> Generated at {now}.", "",
        ]
        for status in sorted(goals_by_status):
            goal_index.extend([f"## {status}", ""])
            for goal in goals_by_status[status]:
                goal_index.append(
                    f"- **P{goal['priority']}** {goal['title']} — {goal['description'][:160]}"
                )
            goal_index.append("")
        _atomic_write(target / "Objectives.generated.md", "\n".join(goal_lines) + "\n")
        _atomic_write(indexes / "Objectives by Status.generated.md",
                      "\n".join(goal_index).rstrip() + "\n")

        home_lines = [
            "# Yon — Knowledge Home", "",
            f"> Automatically refreshed from local SQLite at {now}. SQLite is the source of truth.", "",
            "## Main views",
            "- [[Cognitive Memories.generated|All cognitive memories]]",
            "- [[Memory Graph.generated|Knowledge graph and relationships]]",
            "- [[Objectives.generated|Objectives and progress]]", "",
            "## Organized navigation",
            "- [[Indexes/By Level.generated|By memory level]] — working, episodic, semantic, consolidated",
            "- [[Indexes/By Evidence State.generated|By evidence state]] — confirmed, hypothesis, stale, contested",
            "- [[Indexes/By Source.generated|By source]]",
            "- [[Indexes/Objectives by Status.generated|Objectives by status]]", "",
            "## Reading rules",
            "- **Confirmed** means evidence was recorded; inspect the evidence before relying on it.",
            "- **Hypothesis** is tentative and must not be repeated as fact.",
            "- **Stale** may need refreshing; **contested** has conflicting information.",
            "- Automatically suggested graph links indicate related topics, not factual equivalence.", "",
            "## Current totals",
            f"- Memories exported: {len(memories)}",
            f"- Relationships exported: {sum(len(v) for v in linked.values())}",
            f"- Objectives exported: {len(goals)}",
        ]
        _atomic_write(target / "Home.generated.md", "\n".join(home_lines) + "\n")
        _atomic_write(target / "Cognitive Memories.generated.md", "\n".join(memory_lines) + "\n")

        return {
            "ok": True,
            "files": [
                str(target / "Home.generated.md"),
                str(target / "Cognitive Memories.generated.md"),
                str(target / "Memory Graph.generated.md"),
                str(target / "Objectives.generated.md"),
                str(indexes / "By Level.generated.md"),
                str(indexes / "By Evidence State.generated.md"),
                str(indexes / "By Source.generated.md"),
                str(indexes / "Objectives by Status.generated.md"),
            ],
            "memory_count": len(memories),
            "goal_count": len(goals),
            "relationship_count": sum(len(v) for v in linked.values()),
            "layout": "dashboard_and_grouped_indexes",
        }
    except OSError as exc:
        return {"ok": False, "error": f"Could not export notes: {exc}"}
