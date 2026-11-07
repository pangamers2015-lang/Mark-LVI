"""Query the in-memory status and results of background tasks started by JARVIS."""
from __future__ import annotations


def background_tasks(parameters: dict = None, player=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "list")).strip().lower()
    task_id = str(params.get("task_id", "")).strip()
    getter = getattr(player, "get_background_tasks", None)
    if not callable(getter):
        return "Background task status is unavailable."

    records = getter(task_id if action == "get" else "")
    if action == "get":
        if not task_id:
            return "Provide a task_id."
        if not records:
            return f"No background task was found with ID {task_id}."
        task = records[0]
        result = (
            f"Task {task['id']} ({task['name']}): {task['status']}."
        )
        if task.get("result"):
            result += "\nResult:\n" + str(task["result"])[:12000]
        elif task["status"] == "running":
            result += " It is still running."
        return result

    if action == "list":
        if not records:
            return "There are no background tasks in this session."
        lines = [
            f"{item['id']} — {item['name']} — {item['status']}"
            for item in records
        ]
        return "Background tasks:\n" + "\n".join(lines)

    return "Unknown action. Use 'list' or 'get'."


TOOL = {
    "name": "background_tasks",
    "description": (
        "Checks background work started by JARVIS. Use action='list' when the user "
        "asks what tasks are running or their overall status. Completed background tasks "
        "are automatically announced by Yon at the next safe conversational pause. "
        "Use action='get' with "
        "the exact task_id to retrieve its current status and completed result. "
        "A task ID is returned immediately when long work is started. Never claim "
        "a task is complete until this tool reports completed."
    ),
    "tier": "core",
    "brief": "Lists background tasks and retrieves a task's status or result.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["list", "get"],
                "description": "list all tasks, or get one task by ID"
            },
            "task_id": {
                "type": "STRING",
                "description": "Exact task ID required for action='get'."
            }
        },
        "required": ["action"]
    },
    "handler": background_tasks,
}
