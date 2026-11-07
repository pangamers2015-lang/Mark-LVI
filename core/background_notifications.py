"""User-facing summaries for completed background work.

This module deliberately strips provider/session metadata before a result is
passed back into the live conversation. The provider-to-Yon exchange stays
internal; only the task outcome is announced.
"""
from __future__ import annotations


def _public_result(record: dict) -> str:
    result = str(record.get("result") or "").strip()
    if result.startswith("FCC Cloud completed the task."):
        marker = "Result:\n"
        if marker in result:
            result = result.split(marker, 1)[1].strip()
        else:
            result = ""
    return result[:9000]


def build_task_notification(record: dict) -> str:
    """Build a concise internal handoff that asks the live model to notify the user."""
    if not isinstance(record, dict):
        return ""
    status = str(record.get("status") or "").lower()
    summary = str(record.get("summary") or record.get("name") or "tarefa solicitada").strip()
    result = _public_result(record)

    if status == "completed":
        outcome = "A tarefa em segundo plano foi concluída."
    elif status == "interrupted":
        outcome = "A tarefa em segundo plano foi interrompida antes da conclusão."
    else:
        outcome = "A tarefa em segundo plano terminou com uma falha."

    return (
        "[YON_BACKGROUND_TASK_NOTIFICATION]\n"
        "Este é um aviso interno de conclusão de uma tarefa que o usuário pediu anteriormente; "
        "não é uma nova solicitação e não deve interromper uma resposta que já esteja em andamento. "
        "O sistema aguardou uma pausa segura antes de entregar este aviso. "
        "Informe o usuário naturalmente, em português ou no idioma atual da conversa, "
        "com uma atualização breve. Se houver resultado, apresente o conteúdo útil e concreto; "
        "não mencione prompts, ferramentas internas, IDs de sessão, diretórios ou provedores. "
        "Não invente nem amplie fatos que não estejam no resultado.\n"
        f"Tarefa: {summary[:240]}\n"
        f"Situação: {outcome}\n"
        f"Resultado registrado: {result or 'Nenhum resultado textual foi registrado.'}\\n"
        "[/YON_BACKGROUND_TASK_NOTIFICATION]"
    )
