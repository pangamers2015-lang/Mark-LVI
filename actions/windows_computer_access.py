"""Bounded local Windows inspection for the Yon assistant.

This is a local bridge, not an unrestricted remote shell. It exposes useful
computer context on demand while keeping credentials, command execution and
destructive operations outside this tool.
"""
from __future__ import annotations

import os
import platform
import string
from pathlib import Path


_SENSITIVE_PARTS = {
    ".git", ".ssh", ".gnupg", ".aws", ".azure", ".config",
    "browser data", "user data", "login data", "local state",
}
_SENSITIVE_NAMES = {
    ".env", "api_keys.json", "credentials", "credentials.json",
    "cookies", "login data", "web data", "key4.db", "logins.json",
}
_SKIP_DIRS = {
    "$recycle.bin", "system volume information", "windows", "program files",
    "program files (x86)", "programdata", "appdata", ".git", ".venv",
    "venv", "node_modules", "__pycache__",
}
_MAX_READ = 128 * 1024


def _blocked(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    return bool(parts & _SENSITIVE_PARTS) or name in _SENSITIVE_NAMES


def _system_overview() -> str:
    lines = [
        f"OS: {platform.platform()}",
        f"Computer: {platform.node()}",
        f"User: {os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown'}",
        f"Python: {platform.python_version()}",
        f"Architecture: {platform.machine()}",
    ]
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home().anchor or "/"))
        lines += [
            f"RAM: {mem.total // (1024**3)} GB total; {mem.available // (1024**3)} GB available",
            f"System disk: {disk.percent}% used",
            f"CPU: {psutil.cpu_count(logical=True)} logical processors",
        ]
    except Exception as exc:
        lines.append(f"Detailed hardware metrics unavailable: {exc}")
    return "\n".join(lines)


def _processes(limit: int) -> str:
    try:
        import psutil
    except ImportError:
        return "Process listing requires psutil (already declared in requirements.txt)."
    rows = []
    for proc in psutil.process_iter(["pid", "name", "status", "username"]):
        try:
            info = proc.info
            rows.append((str(info.get("name") or ""), int(info.get("pid") or 0),
                         str(info.get("status") or ""), str(info.get("username") or "")))
        except (psutil.Error, OSError, ValueError):
            continue
    rows.sort(key=lambda item: item[0].casefold())
    return "\n".join(f"{name} | PID {pid} | {status} | {user}"
                     for name, pid, status, user in rows[:limit]) or "No processes found."


def _drives() -> str:
    if platform.system() == "Windows":
        roots = [f"{letter}:\" for letter in string.ascii_uppercase
                 if os.path.exists(f"{letter}:\\")]
        return "Available drive roots: " + (", ".join(roots) if roots else "none detected")
    try:
        import psutil
        return "\n".join(f"{p.device} -> {p.mountpoint} ({p.fstype})"
                         for p in psutil.disk_partitions(all=False))
    except Exception as exc:
        return f"Could not list drives: {exc}"


def _list_directory(raw: str, limit: int) -> str:
    if not raw.strip():
        return "Specify the folder path to inspect."
    folder = Path(raw).expanduser().resolve()
    if _blocked(folder):
        return "This location contains sensitive application or credential data and is not listed."
    if not folder.is_dir():
        return f"Folder not found: {folder}"
    rows = []
    try:
        for child in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
            if child.name.casefold() in _SKIP_DIRS or child.name.startswith("."):
                continue
            kind = "DIR" if child.is_dir() else "FILE"
            try:
                size = child.stat().st_size if child.is_file() else 0
            except OSError:
                size = 0
            rows.append(f"{kind} | {child.name}" + (f" | {size} bytes" if kind == "FILE" else ""))
            if len(rows) >= limit:
                break
    except PermissionError:
        return "Windows denied access to this folder."
    return f"{folder}\n" + ("\n".join(rows) if rows else "(no visible entries)")


def _read_text(raw: str) -> str:
    if not raw.strip():
        return "Specify the exact text-file path to read."
    path = Path(raw).expanduser().resolve()
    if _blocked(path):
        return "Reading credential or sensitive application data is blocked by this tool."
    if not path.is_file():
        return f"File not found: {path}"
    if path.suffix.casefold() not in {
        ".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".yaml",
        ".yml", ".toml", ".xml", ".html", ".css", ".js", ".ts", ".ps1",
        ".bat", ".cmd", ".sql",
    }:
        return "This operation reads text formats only; it will not open binary files."
    if path.stat().st_size > _MAX_READ:
        return f"File exceeds the {_MAX_READ // 1024} KB read limit."
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeError:
        return "File is not valid UTF-8 text."
    return content[:_MAX_READ]


def _search_files(raw: str, query: str, limit: int) -> str:
    if not raw.strip() or len(query.strip()) < 2:
        return "Specify a search folder and a filename fragment of at least two characters."
    root = Path(raw).expanduser().resolve()
    if not root.is_dir() or _blocked(root):
        return "Search folder is missing or protected."
    found, scanned = [], 0
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.casefold() not in _SKIP_DIRS and not d.startswith(".")]
        for filename in files:
            scanned += 1
            if query.casefold() in filename.casefold():
                candidate = Path(current) / filename
                if not _blocked(candidate):
                    found.append(str(candidate))
                    if len(found) >= limit:
                        break
            if scanned >= 10000 or len(found) >= limit:
                break
        if scanned >= 10000 or len(found) >= limit:
            break
    return f"Scanned up to {scanned} file names.\n" + ("\n".join(found) if found else "No matching file names found.")


def windows_computer_access(parameters: dict = None, player=None) -> str:
    p = parameters or {}
    action = str(p.get("action") or "").strip().lower()
    try:
        limit = max(1, min(int(p.get("limit") or 80), 200))
    except (TypeError, ValueError):
        limit = 80
    if action == "system_overview":
        return _system_overview()
    if action == "list_processes":
        return _processes(limit)
    if action == "list_drives":
        return _drives()
    if action == "list_directory":
        return _list_directory(str(p.get("path") or ""), limit)
    if action == "read_text_file":
        return _read_text(str(p.get("path") or ""))
    if action == "search_files":
        return _search_files(str(p.get("path") or ""), str(p.get("query") or ""), limit)
    return "Supported actions: system_overview, list_processes, list_drives, list_directory, read_text_file, search_files."


TOOL = {
    "name": "windows_computer_access",
    "description": (
        "LOCAL COMPUTER INSPECTION tool. Reads Windows system overview, running "
        "process names, available drives, directory contents, selected text files, "
        "and searches file names in a folder. Use it when the user asks what is "
        "installed/running, what files exist, or asks you to inspect their PC. "
        "For installed application discovery use app_inventory first. For opening "
        "apps use open_app; for websites use browser_control; for mouse/keyboard "
        "and visible window interaction use computer_control; for supported file "
        "changes use file_controller. This tool never runs arbitrary shell "
        "commands, never deletes files, and blocks common credential stores. "
        "It reads only the specific path requested, not the whole disk."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "system_overview | list_processes | list_drives | list_directory | read_text_file | search_files"},
            "path": {"type": "STRING", "description": "Exact folder or file path when the action needs one."},
            "query": {"type": "STRING", "description": "Filename fragment for search_files."},
            "limit": {"type": "INTEGER", "description": "Maximum rows/results, 1-200."}
        },
        "required": ["action"]
    },
    "tier": "core",
    "brief": "Inspect the local Windows system, processes, drives and user-selected files.",
    "handler": windows_computer_access,
}
