"""Durable, turn-by-turn conversation continuity for Yon.

This store complements long_term.json (stable personal facts) and learning.sqlite3
(explicit lessons). It records completed user/assistant turns immediately so a
new Live connection can recover recent context without waiting for shutdown.
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "continuity.sqlite3"
_SESSION_ID = uuid.uuid4().hex
_LOCK = threading.RLock()
_MAX_TURNS = 2000
_MAX_TURN_CHARS = 12000


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS conversation_turns ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id TEXT NOT NULL, role TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_turns_created "
        "ON conversation_turns(id DESC)"
    )
    return conn


def record_turn(role: str, content: str) -> bool:
    """Persist one completed user/assistant turn; safe to call on every turn."""
    role = str(role or "").strip().lower()
    text = " ".join(str(content or "").split()).strip()
    if role not in {"user", "assistant"} or not text:
        return False
    text = text[-_MAX_TURN_CHARS:]
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with _LOCK:
            with _connect() as conn:
                conn.execute(
                    "INSERT INTO conversation_turns "
                    "(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (_SESSION_ID, role, text, created_at),
                )
                conn.execute(
                    "DELETE FROM conversation_turns WHERE id NOT IN "
                    "(SELECT id FROM conversation_turns ORDER BY id DESC LIMIT ?)",
                    (_MAX_TURNS,),
                )
        return True
    except sqlite3.Error as exc:
        # Continuity is important, but a storage failure must never kill voice I/O.
        print(f"[Memory] Conversation continuity write failed: {exc}")
        return False


def format_recent_context(limit: int = 16, max_chars: int = 6000) -> str:
    """Return recent completed turns in chronological order for session recovery."""
    try:
        with _LOCK:
            with _connect() as conn:
                rows = conn.execute(
                    "SELECT role, content, created_at FROM conversation_turns "
                    "ORDER BY id DESC LIMIT ?",
                    (max(1, min(int(limit), 40)),),
                ).fetchall()
    except (sqlite3.Error, TypeError, ValueError) as exc:
        print(f"[Memory] Conversation continuity read failed: {exc}")
        return ""

    if not rows:
        return ""

    header = (
        "[RECENT CONVERSATION CONTINUITY — persisted completed turns, newest last. "
        "Use this to resume the current context; if a newer live message conflicts, "
        "the newer message takes precedence.]"
    )
    selected = []
    used = len(header) + 1
    for role, content, created_at in reversed(rows):
        line = f"{str(role).upper()} ({created_at}): {content}"
        if used + len(line) + 1 > max(500, int(max_chars)):
            remaining = max(0, int(max_chars) - used - 1)
            if remaining >= 160:
                selected.append(line[-remaining:])
            break
        selected.append(line)
        used += len(line) + 1

    if not selected:
        return ""
    return header + "\n" + "\n".join(selected) + "\n"
