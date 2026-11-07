from __future__ import annotations

import asyncio
import importlib.util

from ion.providers import GeminiProvider, NvidiaProvider
from ion.providers.nvidia import NVIDIA_LIMITER


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


async def check_ion_health() -> dict:
    """Check the local supervisor runtime and both configured remote providers."""
    providers = {"gemini": GeminiProvider(), "nvidia": NvidiaProvider()}

    async def probe(provider):
        try:
            ok, detail = await provider.health()
            return {"configured": bool(provider.api_key), "reachable": bool(ok), "detail": detail}
        except Exception as exc:
            return {"configured": bool(provider.api_key), "reachable": False,
                    "detail": f"{type(exc).__name__}: {exc}"}

    gemini, nvidia = await asyncio.gather(probe(providers["gemini"]), probe(providers["nvidia"]))
    modules = {
        "microsoft_agent_framework": _installed("agent_framework"),
        "httpx": _installed("httpx"),
        "microphone_sounddevice": _installed("sounddevice"),
        "audio_numpy": _installed("numpy"),
        "desktop_pyqt6": _installed("PyQt6"),
    }
    return {
        "supervisor": "Ion / Microsoft Agent Framework",
        "local_runtime_ready": modules["microsoft_agent_framework"] and modules["httpx"],
        "providers": {"gemini": gemini, "nvidia": nvidia},
        "local_dependencies": modules,
        "nvidia_requests_in_last_minute": NVIDIA_LIMITER.recent_count,
        "nvidia_limit_per_minute": NVIDIA_LIMITER.limit,
    }
