"""Foundational cognitive memory for Yon.

This store complements the existing long-term profile, explicit learning store,
and turn-by-turn continuity database. It adds structured self-model, evidence-
aware knowledge, goals, and resumable checkpoints without replacing them.

SQLite is part of Python's standard library; no additional dependency is needed.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "cognitive.sqlite3"
_LOCK = threading.RLock()

MEMORY_LEVELS = {"working", "episodic", "semantic", "consolidated"}
MEMORY_STATES = {"confirmed", "hypothesis", "stale", "contested"}
GOAL_STATES = {"planned", "active", "blocked", "completed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS self_model (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            state TEXT NOT NULL,
            evidence TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            validated_at TEXT,
            last_accessed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_memories_level_state
            ON memories(level, state, id DESC);
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 3,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_goals_status_priority
            ON goals(status, priority, updated_at DESC);
        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            status TEXT NOT NULL,
            summary TEXT NOT NULL,
            next_step TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_checkpoints_goal
            ON checkpoints(goal_id, id DESC);
        """
    )
    return conn


def initialize() -> bool:
    """Create the schema and seed only Yon's stable, project-approved identity."""
    defaults = {
        "name": "Yon",
        "role": "Personal AI assistant and coordinator",
        "purpose": "Help the user reason, learn, plan, research, and execute tasks safely.",
        "principles": (
            "Preserve existing working systems; make incremental changes; "
            "verify before claiming success; distinguish facts from hypotheses; "
            "ask approval before consequential or destructive actions."
        ),
        "limitations": (
            "Do not claim access to unavailable models, files, devices, or tools. "
            "Do not treat unverified code changes as tested runtime behavior."
        ),
    }
    try:
        with _LOCK, closing(_connect()) as conn, conn:
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO self_model(key,value,source,updated_at) "
                    "VALUES(?,?,?,?)",
                    (key, value, "approved_project_definition", _now()),
                )
        return True
    except sqlite3.Error as exc:
        print(f"[CognitiveMemory] Initialization failed: {exc}")
        return False


def set_identity(key: str, value: str, source: str = "user_or_system") -> bool:
    key, value = str(key or "").strip(), str(value or "").strip()
    if not key or not value or len(key) > 80 or len(value) > 2000:
        return False
    try:
        with _LOCK, closing(_connect()) as conn, conn:
            conn.execute(
                "INSERT INTO self_model(key,value,source,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "source=excluded.source, updated_at=excluded.updated_at",
                (key, value, str(source)[:200], _now()),
            )
        return True
    except sqlite3.Error as exc:
        print(f"[CognitiveMemory] Identity write failed: {exc}")
        return False


def add_memory(
    content: str,
    level: str = "semantic",
    source: str = "unspecified",
    state: str = "hypothesis",
    evidence: str = "",
    validated: bool = False,
) -> int | None:
    content = str(content or "").strip()
    level, state = str(level).lower(), str(state).lower()
    if not content or len(content) > 12000 or level not in MEMORY_LEVELS or state not in MEMORY_STATES:
        return None
    if validated:
        state = "confirmed"
    try:
        with _LOCK, closing(_connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO memories(level,content,source,state,evidence,created_at,validated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (level, content, str(source)[:500], state, str(evidence)[:4000],
                 _now(), _now() if validated else None),
            )
            return int(cur.lastrowid)
    except sqlite3.Error as exc:
        print(f"[CognitiveMemory] Memory write failed: {exc}")
        return None


def set_memory_state(memory_id: int, state: str, evidence: str = "") -> bool:
    state = str(state or "").lower()
    if state not in MEMORY_STATES:
        return False
    try:
        with _LOCK, closing(_connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE memories SET state=?, evidence=?, validated_at=? WHERE id=?",
                (state, str(evidence)[:4000], _now() if state == "confirmed" else None,
                 int(memory_id)),
            )
            return cur.rowcount > 0
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Memory validation failed: {exc}")
        return False


def search_memories(query: str = "", limit: int = 8) -> list[dict[str, Any]]:
    words = [w for w in re.findall(r"\w+", str(query or "").casefold()) if len(w) > 2]
    limit = max(1, min(int(limit), 30))
    try:
        with _LOCK, closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT id,level,content,source,state,evidence,created_at,validated_at "
                "FROM memories ORDER BY id DESC LIMIT 500"
            ).fetchall()
        items = [
            {"id": r[0], "level": r[1], "content": r[2], "source": r[3],
             "state": r[4], "evidence": r[5], "created_at": r[6], "validated_at": r[7]}
            for r in rows
        ]
        if words:
            items = [
                item for item in items
                if any(word in (item["content"] + " " + item["evidence"]).casefold()
                       for word in words)
            ]
        items.sort(key=lambda item: (
            item["state"] == "confirmed",
            item["level"] == "consolidated",
            item["id"],
        ), reverse=True)
        return items[:limit]
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Memory search failed: {exc}")
        return []


def list_memories(limit: int = 500) -> list[dict[str, Any]]:
    """Return recent memories for graph/export views without changing search ranking."""
    try:
        with _LOCK, closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT id,level,content,source,state,evidence,created_at,validated_at "
                "FROM memories ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 2000)),),
            ).fetchall()
        keys = ("id", "level", "content", "source", "state", "evidence", "created_at", "validated_at")
        return [dict(zip(keys, row)) for row in rows]
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Memory listing failed: {exc}")
        return []

def save_goal(
    title: str,
    description: str = "",
    priority: int = 3,
    status: str = "planned",
    goal_id: int | None = None,
) -> int | None:
    title, status = str(title or "").strip(), str(status or "").lower()
    if not title or len(title) > 300 or status not in GOAL_STATES:
        return None
    priority = max(1, min(int(priority), 5))
    try:
        with _LOCK, closing(_connect()) as conn, conn:
            if goal_id is not None:
                cur = conn.execute(
                    "UPDATE goals SET title=?,description=?,priority=?,status=?,updated_at=? WHERE id=?",
                    (title, str(description)[:4000], priority, status, _now(), int(goal_id)),
                )
                return int(goal_id) if cur.rowcount else None
            cur = conn.execute(
                "INSERT INTO goals(title,description,priority,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (title, str(description)[:4000], priority, status, _now(), _now()),
            )
            return int(cur.lastrowid)
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Goal write failed: {exc}")
        return None


def list_goals(include_finished: bool = False, limit: int = 20) -> list[dict[str, Any]]:
    try:
        with _LOCK, closing(_connect()) as conn:
            if include_finished:
                rows = conn.execute(
                    "SELECT id,title,description,priority,status,created_at,updated_at "
                    "FROM goals ORDER BY priority ASC, updated_at DESC LIMIT ?",
                    (max(1, min(int(limit), 100)),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id,title,description,priority,status,created_at,updated_at "
                    "FROM goals WHERE status NOT IN ('completed','cancelled') "
                    "ORDER BY priority ASC, updated_at DESC LIMIT ?",
                    (max(1, min(int(limit), 100)),),
                ).fetchall()
        keys = ("id", "title", "description", "priority", "status", "created_at", "updated_at")
        return [dict(zip(keys, row)) for row in rows]
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Goal read failed: {exc}")
        return []


def save_checkpoint(
    summary: str,
    next_step: str = "",
    goal_id: int | None = None,
    status: str = "in_progress",
    evidence: str = "",
) -> int | None:
    summary = str(summary or "").strip()
    if not summary:
        return None
    try:
        with _LOCK, closing(_connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO checkpoints(goal_id,status,summary,next_step,evidence,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (goal_id, str(status)[:80], summary[:6000], str(next_step)[:2000],
                 str(evidence)[:4000], _now()),
            )
            return int(cur.lastrowid)
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Checkpoint write failed: {exc}")
        return None


def latest_checkpoints(limit: int = 8) -> list[dict[str, Any]]:
    try:
        with _LOCK, closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT id,goal_id,status,summary,next_step,evidence,created_at "
                "FROM checkpoints ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 30)),),
            ).fetchall()
        keys = ("id", "goal_id", "status", "summary", "next_step", "evidence", "created_at")
        return [dict(zip(keys, row)) for row in rows]
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[CognitiveMemory] Checkpoint read failed: {exc}")
        return []


def format_cognitive_context(max_chars: int = 2600) -> str:
    """Compact, evidence-labelled context for a fresh model session."""
    if not initialize():
        return ""
    try:
        with _LOCK, closing(_connect()) as conn:
            identity = conn.execute(
                "SELECT key,value FROM self_model ORDER BY key"
            ).fetchall()
        goals = list_goals(limit=5)
        memories = search_memories(limit=5)
        checkpoints = latest_checkpoints(limit=3)
    except sqlite3.Error as exc:
        print(f"[CognitiveMemory] Context read failed: {exc}")
        return ""

    lines = ["[YON COGNITIVE STATE — persisted structured context]"]
    if identity:
        lines.append("SELF-MODEL:")
        lines.extend(f"- {key}: {value}" for key, value in identity)
    if goals:
        lines.append("ACTIVE GOALS (priority 1 is highest):")
        lines.extend(
            f"- [{g['status']}; P{g['priority']}] {g['title']}: {g['description']}"
            for g in goals
        )
    if memories:
        lines.append("RETRIEVED KNOWLEDGE (state and source matter):")
        lines.extend(
            f"- [{m['level']}; {m['state']}; source={m['source']}] {m['content']}"
            for m in memories
        )
    if checkpoints:
        lines.append("LATEST CHECKPOINTS (resume only after checking current state):")
        lines.extend(
            f"- {c['status']}: {c['summary']} Next: {c['next_step']}"
            for c in checkpoints
        )
    lines.append(
        "Treat confirmed knowledge differently from hypotheses; inspect evidence and "
        "freshness before relying on it. A checkpoint is a record, not proof that work "
        "is still complete. Newer verified information takes precedence."
    )
    result = "\n".join(lines)
    return result[:max(500, int(max_chars))]
