"""Durable local journal for work that must survive an application restart.

The journal stores task intent and progress metadata only; it never assumes that
an interrupted operation is safe to replay. Task-specific resumable workers must
explicitly checkpoint and restore their own state.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_PATH = ROOT / "memory" / "work_journal.json"
_LOCK = threading.RLock()
_MAX_RECORDS = 100


def _read() -> dict:
    try:
        data = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"tasks": []}
    except (OSError, ValueError, TypeError):
        return {"tasks": []}


def _write(data: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = JOURNAL_PATH.with_name(JOURNAL_PATH.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, JOURNAL_PATH)
    finally:
        temp.unlink(missing_ok=True)


def list_tasks() -> list[dict]:
    with _LOCK:
        return [dict(item) for item in _read().get("tasks", []) if isinstance(item, dict)]


def save_task(record: dict) -> None:
    if not isinstance(record, dict) or not record.get("id"):
        return
    with _LOCK:
        data = _read()
        tasks = [x for x in data.get("tasks", []) if isinstance(x, dict)]
        updated = False
        for index, item in enumerate(tasks):
            if item.get("id") == record["id"]:
                tasks[index] = dict(record)
                updated = True
                break
        if not updated:
            tasks.append(dict(record))
        data["tasks"] = tasks[-_MAX_RECORDS:]
        _write(data)


def recover_interrupted() -> list[dict]:
    """Mark work left running by a dead process; do not blindly replay it."""
    recovered = []
    with _LOCK:
        data = _read()
        tasks = data.get("tasks", [])
        changed = False
        for item in tasks:
            if isinstance(item, dict) and item.get("status") == "running":
                item["status"] = "interrupted"
                item["interrupted_at"] = datetime.now().isoformat(timespec="seconds")
                item["recovery"] = "Checkpoint required before safe resume."
                recovered.append(dict(item))
                changed = True
        if changed:
            _write(data)
    return recovered
