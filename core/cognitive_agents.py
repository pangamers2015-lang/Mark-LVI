"""Role contracts for Yon's internal specialist workflow.

These are coordinated roles executed by the configured conversational model and its
existing tools; they are not separate model instances or hidden background processes.
"""
from __future__ import annotations

SPECIALISTS = {
    "planner": {
        "purpose": "Translate the user's goal into ordered, dependency-aware steps.",
        "rules": (
            "Restate the objective and constraints; identify prerequisites, risks, "
            "required approvals and a verifiable definition of done."
        ),
    },
    "researcher": {
        "purpose": "Resolve unknowns using available research and evidence.",
        "rules": (
            "Prefer primary/current sources; distinguish source claims from verified facts; "
            "record dates and conflicts; never fabricate a source or fill evidence gaps by guessing."
        ),
    },
    "executor": {
        "purpose": "Carry out approved steps through existing Yon actions and tools.",
        "rules": (
            "Use existing actions rather than duplicating capabilities; preserve current systems; "
            "request approval for destructive or consequential actions; checkpoint meaningful progress."
        ),
    },
    "reviewer": {
        "purpose": "Independently check whether the requested outcome was actually achieved.",
        "rules": (
            "Compare results with the definition of done; inspect evidence and errors; distinguish "
            "attempted, changed, installed and runtime-tested; reject unsupported success claims."
        ),
    },
}


def specialist_protocol() -> str:
    lines = ["[YON SUPERVISOR AND SPECIALIST ROLES]"]
    for name, spec in SPECIALISTS.items():
        lines.append(f"{name.upper()} — {spec['purpose']} {spec['rules']}")
    lines.append(
        "The supervisor owns the final response and task state. Use these as distinct review "
        "responsibilities within the available model/tool runtime; do not claim independent "
        "models or parallel agents unless they are actually configured and running."
    )
    return "\n".join(lines)


def specialist_assignments(request: str) -> list[dict[str, str]]:
    request = str(request or "").strip()
    return [
        {"role": "planner", "assignment": f"Define the outcome, steps, dependencies and approvals for: {request}"},
        {"role": "researcher", "assignment": "Find and verify missing facts or current information needed by the plan."},
        {"role": "executor", "assignment": "Execute only approved steps using the existing action/tool registry."},
        {"role": "reviewer", "assignment": "Verify each deliverable against evidence and report unresolved gaps."},
    ]
