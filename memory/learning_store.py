# Yon learning store: explicit corrections and durable lessons.
# Uses Python's built-in sqlite3; no extra package is required.
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "memory" / "learning.sqlite3"

_MARKERS = (
    "você errou", "voce errou", "isso está errado", "isso esta errado",
    "não foi isso", "nao foi isso", "eu quis dizer", "eu falei",
    "corrigindo", "correção:", "correcao:", "lembre disso", "lembre-se",
    "guarde isso", "da próxima vez", "da proxima vez", "não faça novamente",
    "nao faca novamente", "o correto é", "o correto e", "that's wrong",
    "you got that wrong", "remember this", "next time", "correction:",
)


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lessons ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, lesson TEXT NOT NULL, "
        "normalized TEXT NOT NULL UNIQUE, source TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lessons_created ON lessons(created_at)")
    return conn


def learn_from_user_text(text: str) -> str:
    """Store only explicit user corrections or instructions to retain a lesson."""
    lesson = " ".join(str(text or "").split()).strip()
    if len(lesson) < 8 or len(lesson) > 1200:
        return ""
    lowered = lesson.casefold()
    if not any(marker in lowered for marker in _MARKERS):
        return ""
    normalized = re.sub(r"\W+", " ", lowered, flags=re.UNICODE).strip()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO lessons(lesson, normalized, source, created_at) "
                "VALUES (?, ?, 'user_correction', ?)",
                (lesson, normalized, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
        return lesson
    except sqlite3.Error as exc:
        print(f"[Memory] Learning store write failed: {exc}")
        return ""


def search_lessons(query: str = "", limit: int = 8) -> list[str]:
    words = [w for w in re.findall(r"\w+", str(query or "").casefold()) if len(w) > 2]
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT lesson FROM lessons ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        lessons = [row[0] for row in rows]
        if not words:
            return lessons[:max(1, min(int(limit), 12))]
        ranked = sorted(
            lessons,
            key=lambda item: sum(word in item.casefold() for word in words),
            reverse=True,
        )
        return [item for item in ranked[:max(1, min(int(limit), 12))]
                if any(word in item.casefold() for word in words)]
    except sqlite3.Error as exc:
        print(f"[Memory] Learning store read failed: {exc}")
        return []


def format_learning_for_prompt(limit: int = 6) -> str:
    lessons = search_lessons(limit=limit)
    if not lessons:
        return ""
    return (
        "[LEARNED FROM USER CORRECTIONS]\n"
        + "\n".join(f"- {lesson}" for lesson in lessons)
        + "\nApply these lessons when relevant; newer explicit corrections override older ones.\n"
    )
