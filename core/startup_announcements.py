"""Persistent, one-time startup announcements for newly integrated capabilities.

Announcements are stored locally and consumed only after the startup greeting is
successfully sent. This works without network access and can be extended whenever
a new capability is added.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANNOUNCEMENTS_PATH = ROOT / "memory" / "startup_announcements.json"
_LOCK = threading.RLock()

_INITIAL_ANNOUNCEMENT = {
    "id": "siftdog-native-research-2026-11-07",
    "title": "Pesquisa web nativa com Siftdog",
    "message": (
        "A pesquisa web nativa do Jarvis foi integrada ao Siftdog, com o "
        "Nemotron responsável pelo planejamento e pela síntese das fontes. "
        "A integração está preparada no projeto; o primeiro teste operacional "
        "deve confirmar a busca real, a extração das páginas e as citações."
    ),
}


def _read() -> dict:
    try:
        data = json.loads(ANNOUNCEMENTS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("announcements"), list):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {"version": 1, "announcements": []}


def _write(data: dict) -> None:
    ANNOUNCEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = ANNOUNCEMENTS_PATH.with_name(
        ANNOUNCEMENTS_PATH.name + "." + uuid.uuid4().hex + ".tmp"
    )
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, ANNOUNCEMENTS_PATH)
    finally:
        temp.unlink(missing_ok=True)


def register_announcement(announcement_id: str, title: str, message: str) -> bool:
    """Queue a new one-time user-facing announcement; return False for duplicates."""
    announcement_id = str(announcement_id or "").strip()
    title = str(title or "").strip()
    message = str(message or "").strip()
    if not announcement_id or not title or not message:
        raise ValueError("announcement_id, title and message are required")
    with _LOCK:
        data = _read()
        items = data["announcements"]
        if any(item.get("id") == announcement_id for item in items if isinstance(item, dict)):
            return False
        items.append({
            "id": announcement_id,
            "title": title,
            "message": message,
            "status": "pending",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        data["announcements"] = items[-100:]
        _write(data)
    return True


def pending_announcements() -> list[dict]:
    """Return pending notices, seeding the initial Siftdog notice exactly once."""
    with _LOCK:
        data = _read()
        items = data["announcements"]
        if not any(
            isinstance(item, dict) and item.get("id") == _INITIAL_ANNOUNCEMENT["id"]
            for item in items
        ):
            items.append({
                **_INITIAL_ANNOUNCEMENT,
                "status": "pending",
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            data["announcements"] = items[-100:]
            _write(data)
        return [
            dict(item) for item in data["announcements"]
            if isinstance(item, dict) and item.get("status", "pending") == "pending"
        ]


def mark_announcements_delivered(announcement_ids: list[str]) -> int:
    """Consume notices only after they have been included in a sent greeting."""
    wanted = {str(item) for item in announcement_ids if item}
    if not wanted:
        return 0
    delivered = 0
    with _LOCK:
        data = _read()
        for item in data["announcements"]:
            if isinstance(item, dict) and item.get("id") in wanted and item.get("status", "pending") == "pending":
                item["status"] = "delivered"
                item["delivered_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
                delivered += 1
        if delivered:
            _write(data)
    return delivered
