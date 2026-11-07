"""Optional bridge to Yon's local specialist model hosted by Ollama.

The active conversation model remains the coordinator. It may consult this model
for an independent analysis, then critically review the result. Ollama is optional
and is never assumed to be installed or available.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_LOCAL_MODEL = "qwen3.5:4b"


def ollama_chat(
    prompt: str,
    model: str | None = None,
    timeout: float | None = None,
    profile: str = "compact",
) -> dict:
    """Ask Ollama for an independent draft.

    By default there is no application-imposed response deadline: long generations
    are allowed to finish. Callers may still pass an explicit timeout for a
    deliberate health check or bounded operation.
    """
    prompt = str(prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "A prompt is required."}

    base = os.environ.get(
        "YON_OLLAMA_URL", "http://127.0.0.1:11434"
    ).rstrip("/")
    model_name = str(
        model or os.environ.get("YON_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
    ).strip()
    if not model_name:
        return {
            "ok": False,
            "error": "Set YON_LOCAL_MODEL or provide a model name installed in Ollama.",
        }

    profile = str(profile or "compact").strip().lower()
    budgets = {"compact": 160, "analysis": 320, "code": 448, "review": 224}
    if profile not in budgets:
        profile = "compact"
    system_prompt = (
        "You are Yon's local specialist, subordinate to the central coordinator. "
        "Answer only the assigned task; be concise and actionable. "
        "Return conclusions and essential evidence or uncertainty only. "
        "Do not greet, repeat context, narrate private reasoning, or invent facts. "
        "Never claim tools, execution, or verification you did not perform. "
        "The coordinator validates your output and owns decisions."
    )
    payload = json.dumps({
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt[:6000]},
        ],
        "options": {"num_predict": budgets[profile], "temperature": 0.2},
        "stream": False,
    }).encode("utf-8")

    request = Request(
        base + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # None means wait for Ollama to finish instead of imposing a fixed timeout.
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        message = data.get("message") or {}
        answer = str(message.get("content") or "").strip()
        if not answer:
            return {
                "ok": False,
                "error": "Ollama returned an empty response.",
                "model": model_name,
            }
        return {
            "ok": True,
            "model": model_name,
            "response": answer[:16000],
            "done_reason": data.get("done_reason"),
        }
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        return {
            "ok": False,
            "error": f"Ollama HTTP {exc.code}: {detail}",
            "model": model_name,
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "error": f"Could not reach local Ollama at {base}: {exc}",
            "model": model_name,
        }
    except (ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": f"Invalid response from Ollama: {exc}",
            "model": model_name,
        }


def ollama_status() -> dict:
    """Return a short, bounded health check and the installed model names."""
    base = os.environ.get(
        "YON_OLLAMA_URL", "http://127.0.0.1:11434"
    ).rstrip("/")
    request = Request(base + "/api/tags", method="GET")
    try:
        with urlopen(request, timeout=3.0) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [
            str(item.get("name") or item.get("model") or "")
            for item in data.get("models", [])
            if isinstance(item, dict)
        ]
        configured = str(
            os.environ.get("YON_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
        ).strip()
        return {
            "ok": True,
            "available": True,
            "base_url": base,
            "configured_model": configured,
            "configured_model_installed": configured in models,
            "models": models,
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "ok": False,
            "available": False,
            "base_url": base,
            "configured_model": str(
                os.environ.get("YON_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
            ).strip(),
            "models": [],
            "error": str(exc),
        }
