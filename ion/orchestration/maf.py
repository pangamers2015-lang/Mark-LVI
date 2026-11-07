from __future__ import annotations

import json

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


class _IonSupervisorExecutor(Executor):
    def __init__(self, supervisor) -> None:
        self.supervisor = supervisor
        super().__init__(id="ion-supervisor")

    @handler
    async def execute(self, payload: str, ctx: WorkflowContext[str, str]) -> None:
        request = json.loads(payload)
        result = await self.supervisor._execute_project(request)
        await ctx.yield_output(json.dumps(result, ensure_ascii=False))


async def run_with_microsoft_agent_framework(supervisor, request: dict) -> dict:
    """Run the Ion supervisor as a Microsoft Agent Framework workflow executor."""
    workflow = WorkflowBuilder(
        start_executor=_IonSupervisorExecutor(supervisor),
        name="IonProjectSupervisor",
        description="Planeja, distribui, testa e encerra tarefas de desenvolvimento do Ion.",
        max_iterations=20,
    ).build()
    events = await workflow.run(json.dumps(request, ensure_ascii=False))
    outputs = events.get_outputs()
    if not outputs:
        raise RuntimeError("O workflow do Microsoft Agent Framework terminou sem resultado.")
    raw = outputs[-1]
    if isinstance(raw, str):
        result = json.loads(raw)
    elif isinstance(raw, dict):
        result = raw
    else:
        result = json.loads(str(raw))
    if not isinstance(result, dict):
        raise RuntimeError("O supervisor retornou um resultado inválido.")
    return result
