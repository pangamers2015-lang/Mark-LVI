"""
Detached self-update worker. It waits for the old app to exit, applies staged
files with backups, launches the new app, and rolls back if startup exits early.
Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def safe_target(root: Path, relative: str) -> Path:
    rel = Path(str(relative).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Unsafe update path: {relative}")
    target = (root / rel).resolve()
    if root.resolve() not in target.parents:
        raise ValueError(f"Update path escapes root: {relative}")
    if any(part in {".git", ".venv", "venv", "__pycache__", ".yon_update", "config"}
           for part in rel.parts):
        raise ValueError(f"Protected update path: {relative}")
    if rel.as_posix() in {"actions/self_updater.py", "core/self_update_runner.py"}:
        raise ValueError(f"Protected update mechanism: {relative}")
    return target


def launch(root: Path) -> subprocess.Popen:
    entry = root / "main.py"
    if not entry.is_file():
        raise FileNotFoundError("main.py is missing; cannot restart the application.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        [sys.executable, str(entry)],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
        start_new_session=(os.name != "nt"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    payload = Path(args.payload).resolve()
    update_dir = root / ".yon_update"
    backup_dir = update_dir / ("backup-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    applied = []
    new_files = []

    # Wait up to 60 seconds for the current UI and its daemon worker to exit.
    deadline = time.monotonic() + 60
    while process_exists(args.wait_pid) and time.monotonic() < deadline:
        time.sleep(0.25)
    if process_exists(args.wait_pid):
        return 2

    try:
        manifest = json.loads(payload.read_text(encoding="utf-8"))
        entries = manifest.get("files")
        if not isinstance(entries, list) or not entries:
            raise ValueError("Empty or invalid update manifest.")

        prepared = []
        for item in entries:
            rel = str(item["path"])
            content = item["content"]
            if not isinstance(content, str):
                raise ValueError(f"Invalid text content for {rel}")
            target = safe_target(root, rel)
            if target.suffix.lower() == ".py":
                compile(content, str(target), "exec")
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".yon-new-" + uuid.uuid4().hex)
            temp.write_text(content, encoding="utf-8", newline="")
            prepared.append((rel, target, temp))

        for rel, target, temp in prepared:
            if target.exists():
                backup = backup_dir / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            else:
                new_files.append(rel)
            os.replace(temp, target)
            applied.append(rel)

        child = launch(root)
        # Give the new process time to initialize its UI and connect its loop.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            code = child.poll()
            if code is not None:
                raise RuntimeError(f"Updated application exited during startup (code {code}).")
            time.sleep(0.5)

        payload.unlink(missing_ok=True)
        return 0

    except Exception:
        # Restore every changed path, and remove files that did not exist before.
        for rel in reversed(applied):
            target = safe_target(root, rel)
            backup = backup_dir / rel
            if backup.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            else:
                target.unlink(missing_ok=True)
        try:
            launch(root)
        except Exception:
            pass
        return 1
    finally:
        for item in update_dir.glob("pending-*.json"):
            if item == payload:
                item.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
