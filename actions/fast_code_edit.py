"""Fast, guarded one-file edits for small, precisely specified code changes.

This action deliberately does not call an LLM. The live model supplies an exact
unique source fragment and its replacement; this handler validates and applies
that patch locally. Ambiguous or multi-file work belongs to dev_agent.
"""
from __future__ import annotations

import os
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
    mode = str(p.get("mode") or "replace").strip().lower()
    folder = str(p.get("folder") or "").strip()
    root = Path(folder).expanduser().resolve() if folder else _base_dir()

    if mode == "search":
        query = str(p.get("query") or "").strip()
        if len(query) < 2:
            return "Fast search needs at least two characters."
        if not root.is_dir():
            return "The selected project folder does not exist."
        allowed = {".py", ".json", ".txt", ".toml", ".yaml", ".yml",
                    ".ini", ".js", ".ts", ".html", ".css"}
        found = []
        scanned = 0
        for candidate in root.rglob("*"):
            if not candidate.is_file() or candidate.suffix.lower() not in allowed:
                continue
            try:
                relative = candidate.relative_to(root)
                if any(part in _BLOCKED or part.startswith(".") for part in relative.parts):
                    continue
                if candidate.stat().st_size > _MAX_BYTES:
                    continue
                scanned += 1
                if scanned > 300:
                    break
                lines = candidate.read_text(encoding="utf-8").splitlines()
                for number, line in enumerate(lines, 1):
                    if query.casefold() in line.casefold():
                        found.append(f"{relative}:{number}: {line.strip()[:240]}")
                        if len(found) >= 30:
                            break
                if len(found) >= 30:
                    break
            except (OSError, UnicodeError):
                continue
        if not found:
            return f"No matches for '{query}' in {scanned} source files."
        return "Search results (read-only; choose an exact unique source fragment before editing):\n" + "\n".join(found)

    if mode != "replace":
        return "Mode must be 'search' or 'replace'."

    raw_path = str(p.get("path") or "").strip()
    old = str(p.get("find_text") or "")
    new = str(p.get("replace_text") or "")

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

        backup_dir = root / ".yon_backups"
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
        return (f"Fast edit applied to {target.relative_to(root)}. "
                f"One exact replacement; backup saved; "
                f"{'Python syntax verified; ' if target.suffix.lower() == '.py' else ''}"
                f"local edit time {elapsed_ms:.1f} ms. "
                "A running module may need a restart before the change takes effect.")
    except Exception as exc:
        return f"Fast edit did not change any file: {exc}"


TOOL = {
    "name": "fast_code_edit",
    "description": (
        "LOW-LEVEL compatibility editor for an exact single-file replacement only. "
        "The default route for software development, project changes, bug fixes and "
        "multi-file tasks is ion_develop_project; do not bypass the Ion supervisor. "
        "Use this tool only when the user explicitly asks for a precise direct edit."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {"type": "STRING", "description": "'search' to locate code without changing files; 'replace' to apply one exact replacement."},
            "query": {"type": "STRING", "description": "Search mode: distinctive code token, such as setWindowTitle."},
            "path": {"type": "STRING", "description": "Replace mode: target file path relative to the project folder."},
            "find_text": {"type": "STRING", "description": "Exact existing source fragment; it must occur exactly once."},
            "replace_text": {"type": "STRING", "description": "Exact replacement source fragment."},
            "folder": {"type": "STRING", "description": "Optional absolute project folder. Defaults to the Yon application folder."}
        },
        "required": []
    },
    "tier": "extra",
    "brief": "Exceptional low-level file replacement only; use ion_develop_project by default.",
    "handler": fast_code_edit,
}
