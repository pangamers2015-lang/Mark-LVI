from __future__ import annotations

import asyncio
import json


def ion_status(parameters: dict, player=None) -> str:
    """Report status of the local MAF runtime, Gemini and NVIDIA providers."""
    try:
        from ion.health import check_ion_health
        result = asyncio.run(check_ion_health())
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"Não foi possível verificar o estado do Ion: {type(exc).__name__}: {exc}"


TOOL = {
    "name": "ion_status",
    "description": (
        "Consulta o estado real da infraestrutura do Ion: Microsoft Agent Framework local, "
        "chaves e conectividade das APIs Gemini e NVIDIA, dependências de voz/áudio e uso do "
        "limite compartilhado de 40 chamadas NVIDIA por minuto. Não inicia tarefas de programação."
    ),
    "parameters": {"type": "OBJECT", "properties": {}},
    "handler": ion_status,
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "tier": "core",
    "brief": "Verifica supervisor local, APIs Gemini/NVIDIA, áudio e limite NVIDIA."
}
