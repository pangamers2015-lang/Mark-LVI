"""Optional bridge to a second LLM hosted locally by Ollama.

The configured conversation model remains the coordinator. Its tool call can ask the
local model for an independent draft/opinion, then the coordinator evaluates it.
No local model is assumed to be installed or available.
"""
from __future__ import annotations
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def ollama_chat(prompt: str, model: str | None = None, timeout: int = 90) -> dict:
    prompt = str(prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "A prompt is required."}
    base = os.environ.get("YON_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model_name = str(model or os.environ.get("YON_LOCAL_MODEL", "")).strip()
    if not model_name:
        return {"ok": False, "error": "Set YON_LOCAL_MODEL or provide a model name installed in Ollama."}
    payload = json.dumps({
        "model": model_name,
        "messages": [
            {"role": "system", "content": (
                "You are Yon's local specialist model. Give a careful independent analysis. "
                "Separate facts from assumptions, state uncertainty, do not claim tool actions "
                "or external verification you did not perform. The coordinator will review you."
            )},
            {"role": "user", "content": prompt[:12000]},
        ],
        "stream": False,
    }).encode("utf-8")
    request = Request(base + "/api/chat", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=max(5, min(int(timeout), 180))) as response:
            data = json.loads(response.read().decode("utf-8"))
        message = data.get("message") or {}
        answer = str(message.get("content") or "").strip()
        if not answer:
            return {"ok": False, "error": "Ollama returned an empty response.", "model": model_name}
        return {"ok": True, "model": model_name, "response": answer[:16000],
                "done_reason": data.get("done_reason")}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        return {"ok": False, "error": f"Ollama HTTP {exc.code}: {detail}", "model": model_name}
    except (URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": f"Could not reach local Ollama at {base}: {exc}"}
    except (ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"Invalid response from Ollama: {exc}", "model": model_name}
