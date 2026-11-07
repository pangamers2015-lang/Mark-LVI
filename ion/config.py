from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """Load a project .env without requiring python-dotenv; process env wins."""
    path = ROOT / ".env"
    if not path.is_file():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


_load_dotenv()


def _saved_keys() -> dict:
    path = ROOT / "config" / "api_keys.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


_SAVED = _saved_keys()


def setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return str(value).strip() if value is not None else default


def api_key(provider: str) -> str:
    names = {
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "nvidia": ("NVIDIA_API_KEY",),
    }.get(provider, ())
    for name in names:
        value = setting(name)
        if value:
            return value
    saved_names = {
        "gemini": ("gemini_api_key", "google_api_key"),
        "nvidia": ("nvidia_api_key",),
    }.get(provider, ())
    for name in saved_names:
        value = str(_SAVED.get(name, "")).strip()
        if value:
            return value
    return ""


def model(provider: str) -> str:
    defaults = {
        "gemini": "gemini-3.8-flash",
        "nvidia": "nvidia/nemotron-3-ultra-550b-a55b",
    }
    key = "GEMINI_MODEL" if provider == "gemini" else "NVIDIA_MODEL"
    return setting(key, defaults[provider])


def planner_provider() -> str:
    value = setting("ION_PLANNER_PROVIDER", "gemini").lower()
    if value not in {"gemini", "nvidia"}:
        return "gemini"
    if api_key(value):
        return value
    other = "nvidia" if value == "gemini" else "gemini"
    return other if api_key(other) else value


def workspace_root() -> Path:
    configured = setting("ION_WORKSPACE_ROOT")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / "Desktop" / "IonProjects").resolve()


def request_timeout() -> float:
    try:
        return max(30.0, min(float(setting("ION_REQUEST_TIMEOUT", "240")), 900.0))
    except ValueError:
        return 240.0


def max_correction_attempts() -> int:
    try:
        return max(0, min(int(setting("ION_MAX_CORRECTION_ATTEMPTS", "2")), 3))
    except ValueError:
        return 2


def nvidia_requests_per_minute() -> int:
    try:
        return max(1, min(int(setting("NVIDIA_RPM_LIMIT", "40")), 40))
    except ValueError:
        return 40
