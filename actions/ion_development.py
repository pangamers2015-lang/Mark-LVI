from __future__ import annotations

import asyncio
import json


def ion_development(parameters: dict, player=None) -> str:
    """Plan and supervise a coding project through the Ion workflow."""
    task = str((parameters or {}).get("task") or "").strip()
    working_directory = str((parameters or {}).get("working_directory") or "").strip()
    if not task:
        return "Informe o que Ion deve desenvolver."
    try:
        from ion.orchestration.supervisor import IonSupervisor
        result = asyncio.run(IonSupervisor().run_project(task, working_directory))
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"Ion não conseguiu concluir a execução: {type(exc).__name__}: {exc}"


TOOL = {
    "name": "ion_develop_project",
    "description": (
        "Use para desenvolver software, criar aplicações, jogos, sites, APIs ou modificar um projeto. "
        "Ion primeiro planeja arquitetura, tecnologias e tarefas; o supervisor Microsoft Agent Framework "
        "distribui as tarefas entre NVIDIA e Gemini, permite implementação paralela em arquivos separados, "
        "executa os testes necessários e devolve falhas ao executor responsável. NVIDIA tem preferência "
        "inicial para código, mas Gemini também programa e corrige. Os dois executam; somente o supervisor testa e aprova. "
        "Informe o pedido completo em task. working_directory é opcional; sem ele, o projeto será criado em Desktop/IonProjects."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {"type": "STRING", "description": "Objetivo completo do projeto ou da alteração."},
            "working_directory": {"type": "STRING", "description": "Pasta do projeto. Opcional; por padrão Desktop/IonProjects."}
        },
        "required": ["task"]
    },
    "handler": ion_development,
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "core",
    "brief": "Ion planeja e supervisor distribui implementação entre NVIDIA e Gemini; o próprio supervisor testa."
}
