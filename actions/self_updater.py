"""
JARVIS action — safely stage code changes to this installation and restart it.

Changes are written only after the current process exits. Python files are syntax
checked before shutdown. Existing files are backed up, writes are atomic, and a
failed restart triggers rollback to the previous files.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE_DIR = ROOT / ".yon_update"
PROTECTED_PARTS = {
    ".git", ".venv", "venv", "__pycache__", ".yon_update",
    "config", "node_modules",
}
PROTECTED_FILES = {
    "actions/self_updater.py",
    "core/self_update_runner.py",
}


def _safe_target(raw: str) -> Path:
    value = str(raw or "").strip().replace("\\", "/")
    candidate = Path(value)
    if not value or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Unsafe relative path: {raw!r}")
    normalized = candidate.as_posix()
    if normalized in PROTECTED_FILES:
        raise ValueError(f"The update mechanism itself is protected: {normalized}")
    if any(part in PROTECTED_PARTS for part in candidate.parts):
        raise ValueError(f"Protected directory in path: {normalized}")
    target = (ROOT / candidate).resolve()
    if ROOT.resolve() not in target.parents:
        raise ValueError(f"Path escapes the application folder: {normalized}")
    if target.exists() and not target.is_file():
        raise ValueError(f"Target is not a regular file: {normalized}")
    return target


def _stage(files: list[dict]) -> tuple[Path, list[str]]:
    if not isinstance(files, list) or not files or len(files) > 20:
        raise ValueError("Provide between 1 and 20 files.")
    staged = []
    seen = set()
    total = 0
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Each file entry must contain path and content.")
        rel = str(item.get("path") or "").replace("\\", "/")
        target = _safe_target(rel)
        if rel in seen:
            raise ValueError(f"Duplicate target path: {rel}")
        seen.add(rel)
        content = item.get("content")
        if not isinstance(content, str):
            raise ValueError(f"Content for {rel} must be text.")
        encoded = content.encode("utf-8")
        total += len(encoded)
        if len(encoded) > 1_000_000:
            raise ValueError(f"File too large: {rel} (1 MB maximum).")
        if target.suffix.lower() == ".py":
            compile(content, str(target), "exec")
        staged.append({"path": rel, "content": content})
    if total > 4_000_000:
        raise ValueError("Combined update exceeds 4 MB.")
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = UPDATE_DIR / f"pending-{uuid.uuid4().hex}.json"
    payload.write_text(json.dumps({"files": staged}, ensure_ascii=False), encoding="utf-8")
    return payload, [entry["path"] for entry in staged]


def self_updater(parameters: dict = None, player=None) -> str:
    params = parameters or {}
    if str(params.get("action", "")).strip().lower() != "apply_and_restart":
        return "Use action='apply_and_restart' with files containing relative paths and complete new file contents."
    try:
        payload, paths = _stage(params.get("files"))
        defer_restart = getattr(player, "defer_restart_until_idle", None)
        if not callable(defer_restart):
            payload.unlink(missing_ok=True)
            return "Update was not started: safe background-task-aware restart is unavailable."
        runner = ROOT / "core" / "self_update_runner.py"
        if not runner.is_file():
            payload.unlink(missing_ok=True)
            raise FileNotFoundError("The protected self-update runner is missing.")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        command = [
            sys.executable, str(runner),
            "--wait-pid", str(os.getpid()),
            "--root", str(ROOT),
            "--payload", str(payload),
        ]
        subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
            start_new_session=(os.name != "nt"),
        )
        # Keep the current process alive while its other background tasks finish.
        # The task-completion hook will close the Qt event loop once the updater
        # is the only remaining work, so no unrelated task is cut off mid-run.
        defer_restart()
        return (
            "Update staged and validated. Restart has been scheduled for "
            + ", ".join(paths)
            + ". The updater will back up the current files, apply the changes "
              "after shutdown, relaunch the app, and roll back if startup fails."
        )
    except Exception as exc:
        return f"Self-update rejected: {type(exc).__name__}: {exc}"


TOOL = {
    "name": "self_updater",
    "description": (
        "Safely updates this running JARVIS installation. Use ONLY when the user "
        "explicitly asks to implement or update this application itself. Supply "
        "action='apply_and_restart' and files as objects with relative 'path' and "
        "complete replacement 'content'. It validates Python syntax, stages the "
        "change, waits for other background tasks to finish, then closes the app, "
        "applies files after process exit and restarts. Existing files are backed up "
        "the update back. Never use for unrelated repositories or arbitrary commands. "
        "Explain which files will change and obtain the user's approval before calling."
    ),
    "brief": (
        "Safely apply approved source-file changes to this app, back up originals, "
        "restart, and roll back if startup fails."
    ),
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["apply_and_restart"],
                "description": "Apply validated file contents after shutting down, then restart."
            },
            "files": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "path": {
                            "type": "STRING",
                            "description": "Path relative to the application root."
                        },
                        "content": {
                            "type": "STRING",
                            "description": "Complete replacement UTF-8 file content."
                        }
                    },
                    "required": ["path", "content"]
                },
                "description": "One or more complete file updates, maximum 20 files and 4 MB total."
            }
        },
        "required": ["action", "files"]
    },
    "handler": self_updater,
}
