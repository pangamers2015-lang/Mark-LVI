"""Run FCC Cloud/Claude Code tasks non-interactively for Yon.

The action uses the installed fcc-claude executable directly (never a shell),
captures its structured JSON result, and runs as a Yon background task.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def _find_executable() -> str:
    configured = os.environ.get("FCC_CLAUDE_PATH", "").strip()
    candidates = [configured] if configured else []
    found = shutil.which("fcc-claude")
    if found:
        candidates.append(found)
    if platform.system() == "Windows":
        candidates.append(str(Path.home() / ".local" / "bin" / "fcc-claude.exe"))
    else:
        candidates.append(str(Path.home() / ".local" / "bin" / "fcc-claude"))

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).expanduser().resolve())
    raise FileNotFoundError(
        "FCC Cloud executable not found. Install fcc-claude or set FCC_CLAUDE_PATH."
    )


def _extract_result(stdout: str) -> dict:
    text = (stdout or "").strip()
    if not text:
        raise RuntimeError("FCC returned no output.")
    # Claude Code's JSON output is normally the entire stdout. Tolerate a
    # harmless launcher line before the JSON object without invoking a shell.
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("FCC did not return the expected JSON result: " + text[:1200])
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise RuntimeError("FCC returned an unexpected JSON structure.")
    return payload


def fcc_cloud(parameters: dict = None, player=None) -> str:
    params = parameters or {}
    task = str(params.get("task") or "").strip()
    if not task:
        return "Provide the task that FCC Cloud should perform."

    executable = _find_executable()
    project_root = Path(__file__).resolve().parent.parent
    requested_cwd = str(params.get("working_directory") or "").strip()
    cwd = Path(requested_cwd).expanduser().resolve() if requested_cwd else project_root
    if not cwd.is_dir():
        return f"FCC task not started: working directory does not exist: {cwd}"

    try:
        timeout = int(params.get("timeout_seconds") or 900)
    except (TypeError, ValueError):
        timeout = 900
    timeout = max(30, min(timeout, 1800))

    command = [
        executable,
        "--permission-mode",
        "auto",
        "--allowedTools",
        "WebSearch,WebFetch",
        "--print",
        "--output-format",
        "json",
        task,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired:
        return (
            f"FCC task timed out after {timeout} seconds. No completion is confirmed. "
            "The process was stopped by the timeout."
        )
    except Exception as exc:
        return f"FCC execution failed: {type(exc).__name__}: {exc}"

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:5000]
        return f"FCC exited with code {completed.returncode}. Details: {detail}"

    try:
        payload = _extract_result(completed.stdout)
    except Exception as exc:
        detail = (completed.stderr or completed.stdout or str(exc)).strip()[:5000]
        return f"FCC output could not be interpreted: {detail}"

    if payload.get("is_error"):
        return "FCC reported an execution error: " + str(payload.get("result") or payload)[:10000]

    result = str(payload.get("result") or "").strip()
    if not result:
        return "FCC completed but returned no textual result."

    details = [
        "FCC Cloud completed the task.",
        f"Working directory: {cwd}",
        f"Session ID: {payload.get('session_id') or 'not supplied'}",
    ]
    usage = payload.get("usage") or {}
    cost = payload.get("total_cost_usd")
    if cost is not None:
        details.append(f"Reported API cost: US$ {cost}")
    details.append("Result:\\n" + result[:16000])
    return "\\n".join(details)


TOOL = {
    "name": "fcc_cloud",
    "description": (
        "Delegate a concrete programming, code investigation, web research, or project-file task "
        "to the user's installed FCC Cloud agent. Runs fcc-claude non-interactively with "
        "structured JSON output, in automatic permission mode with WebSearch and WebFetch "
        "pre-approved so routine web research does not stop for permission prompts. Other "
        "operations are evaluated by Claude Code's automatic safety checks. Does not use "
        "unrestricted permission bypass. The default working directory is the Yon project root. "
        "The action runs in the background; Yon automatically delivers its final result "
        "at the next safe conversational pause. Use background_tasks only when the user "
        "explicitly asks for task status or an earlier retrieval. Do not claim completion "
        "until the task reports completed, and inspect or test resulting changes before "
        "relying on them. Never request or expose API keys or authentication tokens."
    ),
    "brief": "Delegate a programming, investigation, or web research task to FCC Cloud.",
    "tier": "core",
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "Specific task for FCC Cloud to perform."
            },
            "working_directory": {
                "type": "STRING",
                "description": "Optional existing project folder. Defaults to the Yon project root."
            },
            "timeout_seconds": {
                "type": "INTEGER",
                "description": "Maximum execution time, from 30 to 1800 seconds; defaults to 900."
            }
        },
        "required": ["task"]
    },
    "handler": fcc_cloud,
}
