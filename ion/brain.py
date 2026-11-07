from __future__ import annotations

import json
import re
from pathlib import Path

from ion import config
from ion.providers import GeminiProvider, NvidiaProvider
from ion.models import ProjectPlan


def extract_json(text: str) -> dict:
    value = (text or "").strip()
    value = re.sub(r"(?is)<think(?:ing)?>.*?</think(?:ing)?>", "", value).strip()
    value = re.sub(r"^\`\`\`(?:json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*\`\`\`$", "", value)
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("O agente não retornou um objeto JSON válido.")
    parsed = json.loads(value[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("A resposta estruturada não é um objeto JSON.")
    return parsed


class IonBrain:
    """Ion's planning layer; model choice is configurable, not a third agent."""

    def __init__(self) -> None:
        self.providers = {"gemini": GeminiProvider(), "nvidia": NvidiaProvider()}

    def _knowledge_context(self) -> str:
        path = config.ROOT / "knowledge" / "enciclopedia-tecnica-e-motor-de-decisao.txt"
        if not path.is_file():
            return ""
        try:
            limit = int(config.setting("ION_KNOWLEDGE_CONTEXT_CHARS", "18000"))
            return path.read_text(encoding="utf-8")[:max(1000, min(limit, 40000))]
        except (OSError, ValueError):
            return ""

    async def plan(self, request: str) -> ProjectPlan:
        provider_name = config.planner_provider()
        provider = self.providers[provider_name]
        if not config.api_key(provider_name):
            other = "nvidia" if provider_name == "gemini" else "gemini"
            if config.api_key(other):
                provider_name, provider = other, self.providers[other]
            else:
                raise RuntimeError("Configure GEMINI_API_KEY e/ou NVIDIA_API_KEY no arquivo .env.")
        system = (
            "Você é o núcleo de planejamento do Ion. Você decide a arquitetura, linguagem, "
            "frameworks e contratos antes de delegar. Não escreva o código final. Não crie tarefa "
            "de revisão de código: o supervisor testa o resultado. Divida o trabalho em tarefas "
            "pequenas, com arquivos sem sobreposição quando puderem rodar em paralelo. "
            "A NVIDIA é a prioridade inicial de programação, mas distribua trabalho real também "
            "para Gemini quando houver tarefas independentes. Ambos podem programar e corrigir. "
            "Retorne APENAS JSON no esquema solicitado."
        )
        prompt = f"""PEDIDO DO USUÁRIO:
{request}

ENCICLOPÉDIA TÉCNICA JÁ DISPONÍVEL:
{self._knowledge_context()}

Crie um plano executável. Escolha as tecnologias e frameworks adequados e explique as decisões.
Retorne somente JSON com esta estrutura:
{{
  "project_name": "nome_curto_sem_espacos",
  "summary": "resumo do plano",
  "technology_decisions": ["decisão técnica 1"],
  "tasks": [
    {{
      "id": "task-01",
      "title": "título",
      "description": "instruções concretas de implementação",
      "files": ["caminho/relativo/arquivo.ext"],
      "depends_on": [],
      "acceptance_criteria": ["critério objetivo"],
      "validation_commands": ["python -m pytest -q"],
      "preferred_agent": "nvidia"
    }}
  ]
}}

REGRAS:
- Cada tarefa deve indicar exatamente quais arquivos pode criar/alterar.
- Nunca inclua revisão por Gemini ou NVIDIA; eles apenas implementam e corrigem.
- O agente supervisor executará os comandos de validação e decidirá se passou.
- Use dependências para separar tarefas que não podem começar antes de outras.
- Prefira tarefas paralelas com arquivos distintos.
- Inclua NVIDIA e Gemini quando houver pelo menos duas tarefas independentes; dê preferência inicial à NVIDIA para código.
- Os comandos de teste devem usar somente Python/pytest/unittest/compileall, Node --check, npm test/build ou Playwright.
- Não escolha tecnologias que contrariem restrições expressas pelo usuário.
"""
        raw = await provider.complete(system, prompt, json_mode=True)
        return ProjectPlan.from_dict(extract_json(raw))
