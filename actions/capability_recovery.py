"""Automatic recovery workflow for genuine missing Yon capabilities.

This action is called by main.py after explicit unsupported-capability tool results,
or directly by the coordinator when it recognizes that no available tool can perform
a requested real-world operation. It researches only; sandbox work requires approval.
"""
from __future__ import annotations

import json
import re


_BLOCKED_MARKERS = (
    "permission denied", "access denied", "not authorized", "unauthorized",
    "authentication failed", "invalid api key", "invalid token", "rate limit",
    "quota exceeded", "timed out", "timeout", "file not found", "path not found",
    "does not exist", "no such file", "network error", "connection refused",
)

_CAPABILITY_MARKERS = (
    "unknown tool:",
    "not available in this build",
    "not implemented",
    "unsupported operation",
    "unsupported on this platform",
    "not supported on this platform",
    "this platform does not support",
    "platform capability unavailable",
    "missing capability",
    "required capability is unavailable",
    "no tool available",
    "no available tool",
    "cannot access the local filesystem",
    "filesystem access unavailable",
    "file-system access unavailable",
    "not supported by this build",
)


def is_capability_failure(tool_name: str, args: dict | None, result: str) -> bool:
    """Only escalate explicit capability gaps, never ordinary operational failures."""
    text = str(result or "").casefold()
    if not text:
        return False
    if any(marker in text for marker in _BLOCKED_MARKERS):
        return False
    if any(marker in text for marker in _CAPABILITY_MARKERS):
        return True
    if " is not available" in text and any(prefix in text for prefix in ("action '", "plugin '", "tool '")):
        return True
    return text.startswith("unknown tool:")


def _safe_value(key: str, value):
    key_text = str(key).casefold()
    if any(word in key_text for word in ("password", "secret", "token", "api_key", "apikey", "credential")):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _safe_value(k, v) for k, v in list(value.items())[:20]}
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, item) for item in value[:20]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    value = str(value)
    if any(word in key_text for word in ("path", "folder", "directory", "file")):
        value = re.split(r"[\\/]", value.rstrip("\\/"))[-1] or "[local path]"
    return value[:180]


def _safe_failure(value: str) -> str:
    text = str(value or "")[:1800]
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(
        r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]", text
    )
    text = re.sub(r"(?i)[A-Z]:\\Users\\[^\\\s]+", "[LOCAL_USER_PATH]", text)
    return text
def _topic_for(tool_name: str, args: dict) -> str:
    keys = " ".join(str(k).casefold() for k in args)
    values = " ".join(str(v).casefold()[:100] for v in args.values() if isinstance(v, str))
    combined = f"{keys} {values} {tool_name.casefold()}"
    if any(word in combined for word in ("folder", "directory", "file_path", "filesystem", "file system")):
        return "local filesystem and folder access"
    if any(word in combined for word in ("browser", "website", "webpage")):
        return "browser interaction and web navigation"
    if any(word in combined for word in ("screen", "window", "mouse", "keyboard", "desktop")):
        return "desktop interaction and control"
    return f"missing capability for {str(tool_name)[:80]}"


def _cloud_result_text(result: str) -> str:
    marker = "Result:\n"
    if marker in result:
        return result.split(marker, 1)[1].strip()[:14000]
    return str(result or "").strip()[:14000]


def _structured_findings(text: str) -> dict:
    candidate = text.strip()
    fence = chr(96) * 3
    if candidate.startswith(fence):
        candidate = re.sub(r"^" + fence + r"(?:json)?\s*|\s*" + fence + r"$", "", candidate, flags=re.I)
    start, end = candidate.find("{"), candidate.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(candidate[start:end + 1])
            if isinstance(value, dict):
                return value
        except (ValueError, TypeError):
            pass
    return {}


def capability_recovery(parameters: dict, player=None) -> str:
    p = parameters or {}
    task = _safe_failure(str(p.get("task") or "").strip())
    limitation = _safe_failure(str(p.get("limitation") or p.get("failure_result") or ""))
    failed_tool = str(p.get("failed_tool") or "not identified").strip()[:100]
    raw_args = p.get("failed_args") if isinstance(p.get("failed_args"), dict) else {}
    safe_args = {str(k): _safe_value(k, v) for k, v in list(raw_args.items())[:30]}
    topic = str(p.get("topic") or _topic_for(failed_tool, safe_args)).strip()[:500]

    if not task or not limitation:
        return "Capability investigation requires the user's task and a concrete technical limitation."

    try:
        from actions.capability_development import active_proposal_for_topic, capability_development
        from actions.fcc_cloud import fcc_cloud

        existing = active_proposal_for_topic(topic)
        if existing:
            return (
                "An update note for this capability is already active. Do not repeat the Cloud research.\\n"
                + existing
            )
        rejected = capability_development({"action": "rejected_approaches", "topic": topic})
        cloud_task = (
            "Research a technical capability gap for the Yon desktop assistant. This is a RESEARCH-ONLY task. "
            "Do not edit, create, delete, install, execute, or modify any files or environments. "
            "Do not access secrets, credentials, private user documents, or unrelated folders. "
            "The user's requested operation (short description): " + task[:500] + "\n"
            "Tool that failed: " + failed_tool + "\n"
            "Sanitized tool arguments: " + json.dumps(safe_args, ensure_ascii=False)[:1800] + "\n"
            "Observed limitation: " + limitation + "\n"
            "Capability topic: " + topic + "\n"
            "Previously rejected approaches (avoid these exact approaches; suggest a materially different "
            "solution only if appropriate): " + str(rejected)[:1800] + "\n\n"
            "Investigate the smallest practical safe solution. Prefer built-in Windows/Python APIs and "
            "already-installed project capabilities before third-party packages. If a dependency or GitHub "
            "project is truly needed, identify its authoritative source, license, maintenance status, "
            "security implications and installation requirements. Explain what Yon can implement locally. "
            "Return ONLY a JSON object with keys: title, topic, limitation, approach, implementation_plan, "
            "risks, dependencies, test_plan, sources. Keep each field concise but specific. "
            "Do not claim you tested anything. Do not make changes."
        )
        cloud_response = fcc_cloud({"task": cloud_task, "timeout_seconds": 600})
        if not str(cloud_response).startswith("FCC Cloud completed the task."):
            return (
                "Automatic capability investigation could not obtain a research result from FCC Cloud. "
                + str(cloud_response)[:2500]
            )

        findings = _cloud_result_text(str(cloud_response))
        data = _structured_findings(findings)
        title = str(data.get("title") or f"Nova capacidade: {topic}")[:200]
        approach = str(data.get("approach") or "Adotar a solução técnica pesquisada pelo FCC; consultar os achados completos antes de implementar.")[:1200]
        proposal = capability_development({
            "action": "propose",
            "title": title,
            "topic": str(data.get("topic") or topic)[:500],
            "limitation": str(data.get("limitation") or limitation)[:2000],
            "approach": approach,
            "cloud_findings": findings[:6000],
            "implementation_plan": str(data.get("implementation_plan") or findings)[:6000],
            "risks": str(data.get("risks") or "Revisar permissões, origem do código e impacto antes da instalação.")[:4000],
            "dependencies": str(data.get("dependencies") or "A confirmar após revisão da proposta.")[:2000],
            "test_plan": str(data.get("test_plan") or "Criar ambiente isolado, testar sem tocar no Yon principal e registrar evidências.")[:4000],
        })
        return (
            "AUTOMATIC CAPABILITY INVESTIGATION FINISHED\n"
            + proposal
            + "\nThe Cloud research was internal. Only this update note should be shown to the user. "
              "No sandbox was created, no dependencies were installed, and no production files were changed."
        )
    except Exception as exc:
        return f"Automatic capability investigation failed safely: {type(exc).__name__}: {exc}"


TOOL = {
    "name": "capability_recovery",
    "description": (
        "Automatically investigate a genuine missing technical capability when the user requested a real "
        "operation and no available Yon tool can perform it, or when the application reports an explicit "
        "unsupported-capability failure. This is NOT for definitions, trivia, ordinary questions, transient "
        "errors, missing files, permission denials, authentication failures or rate limits. Consults FCC Cloud "
        "in the background for research only, checks previously rejected approaches, and creates an update "
        "note through capability_development. It never installs dependencies, creates a sandbox, executes "
        "downloaded code or edits production files. The note must be presented to the user for approval."
    ),
    "brief": "Researches genuine missing capabilities and prepares an approval note.",
    "tier": "core",
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {"type": "STRING"},
            "limitation": {"type": "STRING"},
            "failed_tool": {"type": "STRING"},
            "failed_args": {"type": "OBJECT"},
            "failure_result": {"type": "STRING"},
            "topic": {"type": "STRING"},
        },
        "required": ["task", "limitation"],
    },
    "handler": capability_recovery,
}
