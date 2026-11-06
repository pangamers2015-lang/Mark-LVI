"""
JARVIS action — run a program without showing a terminal window, or open a
file/folder with the operating system's default application.

This is a process-launch utility, not a shell:
- programs are started with an argument vector (never shell=True);
- Windows console processes use CREATE_NO_WINDOW;
- standard input/output/error are detached from the assistant's UI;
- open_path uses the OS file association directly, without CMD/PowerShell.
The requested GUI application still appears when opening a file or folder.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from pathlib import Path


_SYSTEM = platform.system()

# Do not turn this utility into an interactive terminal or shell.
_BLOCKED_TERMINALS = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "bash.exe", "sh.exe",
    "zsh", "fish", "wt.exe", "windowsterminal.exe",
}


def _resolve_program(value: str) -> str:
    raw = str(value or "").strip().strip('"')
    if not raw:
        raise ValueError("No program was specified.")

    candidate = Path(raw).expanduser()
    if candidate.is_file():
        resolved = str(candidate.resolve())
    else:
        found = shutil.which(raw)
        if not found:
            raise FileNotFoundError(
                f"Program '{raw}' was not found. Provide its executable path or a name on PATH."
            )
        resolved = str(Path(found).resolve())

    if Path(resolved).name.casefold() in _BLOCKED_TERMINALS:
        raise ValueError(
            "Interactive command shells and terminal emulators are not supported by this tool. "
            "Use a dedicated application or executable instead."
        )
    return resolved


def _open_path(path_value: str) -> str:
    raw = str(path_value or "").strip().strip('"')
    if not raw:
        raise ValueError("No file or folder path was specified.")

    target = Path(raw).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")
    target = target.resolve()

    if _SYSTEM == "Windows":
        # ShellExecute file association; this does not create a CMD window.
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif _SYSTEM == "Darwin":
        subprocess.Popen(
            ["open", str(target)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    elif _SYSTEM == "Linux":
        opener = shutil.which("xdg-open")
        if not opener:
            raise RuntimeError("xdg-open is not installed on this Linux system.")
        subprocess.Popen(
            [opener, str(target)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    else:
        raise RuntimeError(f"Unsupported operating system: {_SYSTEM}")

    return (
        f"Sent the path to the operating system's default application: {target}. "
        "No command terminal was opened; the requested application may appear on screen."
    )


def _launch_program(
    program: str,
    arguments: list[str] | None = None,
    working_directory: str = "",
    wait_seconds: float = 0.0,
) -> str:
    executable = _resolve_program(program)
    args = arguments or []
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ValueError("Arguments must be a list of text values.")
    if len(args) > 40 or any(len(a) > 4000 for a in args):
        raise ValueError("Too many arguments or an argument is too long.")

    cwd = None
    if working_directory:
        work = Path(working_directory).expanduser().resolve()
        if not work.is_dir():
            raise NotADirectoryError(f"Working directory does not exist: {work}")
        cwd = str(work)

    try:
        wait = max(0.0, min(float(wait_seconds or 0.0), 10.0))
    except (TypeError, ValueError):
        wait = 0.0

    creationflags = 0
    if _SYSTEM == "Windows":
        # Suppresses a console window for console-subsystem executables.
        # GUI applications keep their own normal visible window.
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    process = subprocess.Popen(
        [executable, *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        start_new_session=(_SYSTEM != "Windows"),
    )

    if wait:
        time.sleep(wait)
        return_code = process.poll()
        if return_code is not None:
            return (
                f"Started {Path(executable).name} (PID {process.pid}); "
                f"it exited after the check with code {return_code}. "
                "No terminal window was shown."
            )

    return (
        f"Started {Path(executable).name} in the background (PID {process.pid}). "
        "No terminal window was shown. The process was started, but completion "
        "has not been confirmed."
    )


def background_executor(parameters: dict = None, player=None) -> str:
    """Start a process without an interactive terminal, or open a path normally."""
    params = parameters or {}
    action = str(params.get("action", "")).strip().lower()

    try:
        if action == "open_path":
            return _open_path(params.get("path", ""))

        if action == "launch_program":
            return _launch_program(
                program=params.get("program", ""),
                arguments=params.get("arguments", []),
                working_directory=params.get("working_directory", ""),
                wait_seconds=params.get("wait_seconds", 0.0),
            )

        return (
            "Unknown action. Use 'open_path' to open a file/folder with its default "
            "application, or 'launch_program' to start an executable without a terminal."
        )
    except Exception as exc:
        print(f"[BackgroundExecutor] {type(exc).__name__}: {exc}")
        return f"Background execution failed: {type(exc).__name__}: {exc}"


TOOL = {
    "name": "background_executor",
    "description": (
        "Starts a program without showing a CMD/PowerShell/terminal window, or opens "
        "a local file/folder through the operating system's default application. "
        "Use action='open_path' with 'path' when the user wants a file or folder opened "
        "without typing its path into CMD. The requested viewer/application still opens "
        "normally on screen; only the command terminal is avoided. Use action='launch_program' "
        "with 'program' and optional 'arguments' (a list of separate argument strings) to "
        "start a background executable. This is NOT a shell: never pass a whole command line, "
        "never use shell syntax, and never claim a long-running task completed just because "
        "a process started. Interactive command shells and terminal emulators are blocked."
    ),
    "brief": (
        "Opens files/folders without CMD, or launches an executable in the background "
        "with no terminal window. Uses separate program and argument fields, not shell commands."
    ),
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["open_path", "launch_program"],
                "description": "open_path | launch_program"
            },
            "path": {
                "type": "STRING",
                "description": "Existing local file or folder path for action='open_path'."
            },
            "program": {
                "type": "STRING",
                "description": "Executable name on PATH or full executable path for action='launch_program'."
            },
            "arguments": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Optional list of separate command-line arguments for the executable; do not combine into one shell command."
            },
            "working_directory": {
                "type": "STRING",
                "description": "Optional existing folder to use as the process working directory."
            },
            "wait_seconds": {
                "type": "NUMBER",
                "description": "Optional check delay from 0 to 10 seconds. Use 0 for immediate background return."
            }
        },
        "required": ["action"]
    },
    "handler": background_executor,
}
