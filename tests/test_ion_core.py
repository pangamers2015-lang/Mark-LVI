from __future__ import annotations

import unittest
from typing import Never

from ion.brain import extract_json
from ion.models import ProjectPlan
from ion.orchestration.supervisor import _safe_relative


class IonPlanningTests(unittest.TestCase):
    def test_extracts_json_from_plain_response(self):
        result = extract_json('{"tasks": []}')
        self.assertEqual(result, {"tasks": []})

    def test_project_plan_parses_task_contract(self):
        plan = ProjectPlan.from_dict({
            "project_name": "demo",
            "summary": "demo project",
            "technology_decisions": ["HTML"],
            "tasks": [{
                "id": "task-01",
                "title": "Create page",
                "description": "Create a web page",
                "files": ["index.html"],
                "depends_on": [],
                "acceptance_criteria": ["Page exists"],
                "validation_commands": [],
                "preferred_agent": "nvidia",
            }],
        })
        self.assertEqual(plan.project_name, "demo")
        self.assertEqual(plan.tasks[0].files, ["index.html"])

    def test_workspace_path_guard(self):
        self.assertEqual(_safe_relative("src/main.py"), "src/main.py")
        for value in ("../escape.py", ".env", "config/api_keys.json", ".git/config"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _safe_relative(value)


class MicrosoftAgentFrameworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_supervisor_workflow_executes(self):
        from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

        class EchoExecutor(Executor):
            def __init__(self):
                super().__init__(id="ion-maf-smoke-test")

            @handler
            async def run(self, value: str, ctx: WorkflowContext[Never, str]) -> None:
                await ctx.yield_output(value.upper())

        workflow = WorkflowBuilder(start_executor=EchoExecutor(), name="IonSmokeTest").build()
        events = await workflow.run("ion")
        self.assertEqual(events.get_outputs(), ["ION"])


if __name__ == "__main__":
    unittest.main()
