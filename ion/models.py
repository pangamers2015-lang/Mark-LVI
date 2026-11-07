from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WorkTask:
    id: str
    title: str
    description: str
    files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    preferred_agent: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WorkTask":
        return cls(
            id=str(value.get("id") or "").strip(),
            title=str(value.get("title") or "").strip(),
            description=str(value.get("description") or "").strip(),
            files=[str(x).replace("\\", "/") for x in value.get("files", []) if str(x).strip()],
            depends_on=[str(x) for x in value.get("depends_on", [])],
            acceptance_criteria=[str(x) for x in value.get("acceptance_criteria", [])],
            validation_commands=[str(x) for x in value.get("validation_commands", [])],
            preferred_agent=str(value.get("preferred_agent") or "").lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectPlan:
    project_name: str
    summary: str
    technology_decisions: list[str]
    tasks: list[WorkTask]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProjectPlan":
        tasks = [WorkTask.from_dict(x) for x in value.get("tasks", []) if isinstance(x, dict)]
        return cls(
            project_name=str(value.get("project_name") or "ion_project"),
            summary=str(value.get("summary") or ""),
            technology_decisions=[str(x) for x in value.get("technology_decisions", [])],
            tasks=tasks,
        )
