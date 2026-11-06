"""Fast, guarded one-file edits for small, precisely specified code changes.

This action deliberately does not call an LLM. The live model supplies an exact
unique source fragment and its replacement; this handler validates and applies
that patch locally. Ambiguous or multi-file work belongs to dev_agent.
"""
from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path


def _base_dir() -> Path:
    if getattr(__import__("sys"), "frozen", False):
        return Path(__import__("sys").executable).parent.resolve()
    return Path(__file__).resolve().parent.parent


_BLOCKED = {".git", ".venv", "venv", "node_modules", "__pycache__",
            ".yon_update", ".yon_backups", "config"}
_MAX_BYTES = 1_000_000


def _resolve_target(raw_path: str, folder: str = "") -> Path:
    root = Path(folder).expanduser().resolve() if folder else _base_dir()
    if not root.is_dir():
        raise ValueError("The selected project folder does not exist.")
    candidate = (root / raw_path).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise ValueError("The target must stay inside the selected project folder.")
    if any(part in _BLOCKED for part in relative.parts):
        raise ValueError("This protected folder cannot be edited by the fast editor.")
    if not candidate.is_file():
        raise ValueError("The target file does not exist.")
    if candidate.stat().st_size > _MAX_BYTES:
        raise ValueError("The target file exceeds the 1 MB fast-edit limit.")
    return candidate


def fast_code_edit(parameters: dict, player=None, speak=None) -> str:
    p = parameters or {}
    started = time.perf_counter()
    raw_path = str(p.get("path") or "").strip()
    old = str(p.get("find_text") or "")
    new = str(p.get("replace_text") or "")
    folder = str(p.get("folder") or "").strip()

    if not raw_path or not old:
        return "Fast edit needs a relative file path and the exact existing text."
    if old == new:
        return "No change needed: the replacement is identical."
    if len(old) > 20000 or len(new) > 20000:
        return "The fast editor accepts source fragments up to 20,000 characters."

    try:
        target = _resolve_target(raw_path, folder)
        original = target.read_text(encoding="utf-8")
        occurrences = original.count(old)
        if occurrences != 1:
            return (f"Fast edit stopped safely: the exact source fragment occurs "
                    f"{occurrences} times; exactly one occurrence is required. "
                    "Use the full coding agent to investigate.")
        updated = original.replace(old, new, 1)

        if target.suffix.lower() == ".py":
            try:
                compile(updated, str(target), "exec")
            except SyntaxError as exc:
                return (f"Fast edit rejected: the replacement would create a "
                        f"Python syntax error at line {exc.lineno}: {exc.msg}")

        backup_dir = _base_dir() / ".yon_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = backup_dir / f"{target.name}.{stamp}-{time.time_ns() % 1000000:06d}.bak"
        backup.write_text(original, encoding="utf-8")

        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp",
                                         dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        return (f"Fast edit applied to {target.relative_to(_base_dir())}. "
                f"One exact replacement; backup saved; "
                f"{'Python syntax verified; ' if target.suffix.lower() == '.py' else ''}"
                f"local edit time {elapsed_ms:.1f} ms. "
                "A running module may need a restart before the change takes effect.")
    except Exception as exc:
        return f"Fast edit did not change any file: {exc}"


TOOL = {
    "name": "fast_code_edit",
    "description": (
        "FAST LOCAL CODE EDITOR for SIMPLE, SMALL changes to ONE existing file. "
        "Use this INSTEAD OF dev_agent when the requested change is a small, "
        "unambiguous one-file edit AND you already know the exact existing source "
        "text and exact replacement (for example changing one window-title string, "
        "label, colour literal, constant or setting). This action performs no model "
        "generation: it checks that the exact fragment occurs once, makes a backup, "
        "writes atomically and checks Python syntax. Supply path relative to the "
        "project folder, exact find_text, replace_text, and optional folder. "
        "Do NOT guess source text or paths. If you need to inspect/investigate, "
        "if the fragment is unknown/ambiguous, if more than one file is needed, "
        "or if the change requires design/refactoring/testing, use dev_agent instead. "
        "A successful file edit does not hot-reload a module already running."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING", "description": "Target file path relative to the project folder."},
            "find_text": {"type": "STRING", "description": "Exact existing source fragment; it must occur exactly once."},
            "replace_text": {"type": "STRING", "description": "Exact replacement source fragment."},
            "folder": {"type": "STRING", "description": "Optional absolute project folder. Defaults to the Yon application folder."}
        },
        "required": ["path", "find_text", "replace_text"]
    },
    "tier": "core",
    "brief": "Apply one exact, unique local source replacement with backup and syntax validation.",
    "handler": fast_code_edit,
}
