"""Native, citation-first web research for Jarvis.

Architecture: LangGraph orchestration -> bounded shallow or multi-phase deep
research -> Tavily (the sole web-search provider) -> NVIDIA Nemotron synthesis.
No FCC, Qwen, browser automation, or external agent is used by this pipeline.
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import TypedDict

import requests
from bs4 import BeautifulSoup
from langgraph.graph import END, StateGraph

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
TAVILY_URL = "https://api.tavily.com/search"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
TIMEOUT = (8, 55)
MAX_RESULTS = 8
MAX_PAGE_CHARS = 9000


class ResearchState(TypedDict, total=False):
    query: str
    mode: str
    depth: str
    plan: list[str]
    results: list[dict]
    notes: list[dict]
    answer: str
    error: str


def _keys() -> dict:
    try:
        from memory.config_manager import load_api_keys
        return load_api_keys() or {}
    except Exception:
        return {}


def _credential(name: str, config_name: str) -> str:
    return (os.environ.get(name) or str(_keys().get(config_name) or "")).strip()


def _chat(messages: list[dict], *, max_tokens: int = 2200, temperature: float = 0.2) -> str:
    key = _credential("NVIDIA_API_KEY", "nvidia_api_key")
    if not key:
        raise RuntimeError(
            "Pesquisa nativa não configurada: adicione nvidia_api_key em "
            "config/api_keys.json ou defina NVIDIA_API_KEY."
        )
    model = os.environ.get("JARVIS_RESEARCH_MODEL", DEFAULT_MODEL).strip()
    response = requests.post(
        NVIDIA_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": True},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("NVIDIA NIM não retornou uma resposta utilizável.")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, list):
        content = "\n".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Nemotron retornou conteúdo vazio.")
    return content.strip()


def _tavily_search(query: str, *, deep: bool = False, limit: int = 6) -> list[dict]:
    key = _credential("TAVILY_API_KEY", "tavily_api_key")
    if not key:
        raise RuntimeError(
            "Pesquisa web não configurada: adicione tavily_api_key em "
            "config/api_keys.json ou defina TAVILY_API_KEY."
        )
    response = requests.post(
        TAVILY_URL,
        json={
            "api_key": key,
            "query": query,
            "search_depth": "advanced" if deep else "basic",
            "topic": "general",
            "max_results": max(1, min(limit, 10)),
            "include_answer": False,
            "include_raw_content": "markdown",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results") or []:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url.startswith(("https://", "http://")) or not title:
            continue
        results.append({
            "title": title,
            "url": url,
            "content": str(item.get("content") or "")[:5000],
            "raw_content": str(item.get("raw_content") or "")[:MAX_PAGE_CHARS],
            "score": item.get("score"),
        })
    return results


def _read_page(item: dict) -> dict:
    if item.get("raw_content"):
        return item
    try:
        response = requests.get(
            item["url"],
            headers={"User-Agent": "JarvisResearch/1.0 (+citation research)"},
            timeout=(6, 14),
        )
        response.raise_for_status()
        if "text/html" not in response.headers.get("content-type", "").lower():
            return item
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            node.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        item["raw_content"] = text[:MAX_PAGE_CHARS]
    except Exception:
        item["raw_content"] = item.get("content", "")
    return item


def _dedupe(items: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for item in items:
        url = item.get("url")
        if url and url not in seen:
            seen.add(url)
            unique.append(item)
    return unique


def _orchestrate(state: ResearchState) -> dict:
    mode = state.get("mode", "auto").lower()
    query = state["query"]
    deep = mode in {"research", "deep"}
    if mode == "auto":
        deep = len(query.split()) > 16 or bool(re.search(
            r"(?i)\b(compare|comprehensive|in depth|deep|detalhad[oa]|aprofundad[oa]|"
            r"análise completa|relatório|investigue|investigar)\b", query
        ))
    return {"depth": "deep" if deep else "shallow"}


def _shallow_research(state: ResearchState) -> dict:
    results = _tavily_search(state["query"], deep=False, limit=6)
    if not results:
        raise RuntimeError("Tavily não encontrou fontes para essa consulta.")
    with ThreadPoolExecutor(max_workers=4) as pool:
        notes = list(pool.map(_read_page, results[:4]))
    prompt = (
        "Responda à pergunta usando somente as evidências fornecidas. "
        "Priorize fatos atuais, diferencie datas de publicação e datas dos eventos, "
        "aponte divergências e não invente dados. Inclua citações inline [1], [2] "
        "e uma seção Fontes com os mesmos números e URLs. Se as fontes não bastarem, "
        "declare a limitação. Responda em português brasileiro.\n\n"
        f"PERGUNTA: {state['query']}\n\nEVIDÊNCIAS:\n{_format_sources(notes)}"
    )
    return {"results": results, "notes": notes, "answer": _chat(
        [{"role": "system", "content": "Você é o pesquisador rápido do Jarvis. Seja preciso e cite fontes."},
         {"role": "user", "content": prompt}],
        max_tokens=1800,
    )}


def _plan_deep(state: ResearchState) -> dict:
    raw = _chat(
        [{"role": "system", "content": (
            "Você planeja pesquisas web. Crie de 3 a 5 consultas independentes, "
            "complementares e específicas para responder à pergunta. Cubra contexto, "
            "dados atuais, fontes primárias e possíveis controvérsias. Retorne somente "
            "JSON válido no formato {\"queries\":[...]}. Consultas em português ou inglês "
            "conforme a melhor cobertura."
        )},
         {"role": "user", "content": state["query"]}],
        max_tokens=700,
        temperature=0.1,
    )
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        parsed = json.loads(match.group(0)) if match else {}
        queries = [str(q).strip() for q in parsed.get("queries", []) if str(q).strip()]
    except (ValueError, TypeError):
        queries = []
    queries = list(dict.fromkeys(queries))[:5]
    if len(queries) < 2:
        queries = [state["query"], f"{state['query']} fontes oficiais dados recentes"]
    return {"plan": queries}


def _deep_search(state: ResearchState) -> dict:
    queries = state.get("plan") or [state["query"]]
    gathered = []
    # Bounded parallel workers: one Tavily provider, several independent research angles.
    with ThreadPoolExecutor(max_workers=min(4, len(queries))) as pool:
        futures = {pool.submit(_tavily_search, q, deep=True, limit=5): q for q in queries}
        for future in as_completed(futures):
            gathered.extend(future.result())
    results = _dedupe(gathered)[:12]
    if not results:
        raise RuntimeError("Tavily não encontrou fontes para a pesquisa aprofundada.")
    with ThreadPoolExecutor(max_workers=6) as pool:
        notes = list(pool.map(_read_page, results[:8]))
    return {"results": results, "notes": notes}


def _format_sources(sources: list[dict]) -> str:
    blocks = []
    for index, item in enumerate(sources, 1):
        excerpt = item.get("raw_content") or item.get("content") or ""
        blocks.append(
            f"[{index}] {item.get('title', 'Fonte')}\nURL: {item.get('url', '')}\n"
            f"EVIDÊNCIA: {excerpt[:MAX_PAGE_CHARS]}"
        )
    return "\n\n".join(blocks)


def _write_deep(state: ResearchState) -> dict:
    prompt = (
        "Produza um relatório de pesquisa aprofundada, claro e bem estruturado, "
        "respondendo à pergunta. Sintetize evidências de fontes independentes, "
        "separe fatos confirmados de inferências, sinalize divergências e lacunas, "
        "considere datas e contexto. Não invente números, citações ou conclusões. "
        "Use citações inline [1], [2] e seção Fontes com título e URL correspondentes. "
        "Responda em português brasileiro.\n\n"
        f"PERGUNTA: {state['query']}\n\nPLANO: {json.dumps(state.get('plan', []), ensure_ascii=False)}"
        f"\n\nFONTES E EVIDÊNCIAS:\n{_format_sources(state.get('notes', []))}"
    )
    answer = _chat(
        [{"role": "system", "content": (
            "Você é o pesquisador principal do Jarvis. Faça síntese crítica, "
            "rastreável e baseada em evidências; não extrapole as fontes."
        )},
         {"role": "user", "content": prompt}],
        max_tokens=5000,
        temperature=0.15,
    )
    return {"answer": answer}


def _route(state: ResearchState) -> str:
    return "deep_plan" if state.get("depth") == "deep" else "shallow"


def _build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("orchestrate", _orchestrate)
    graph.add_node("shallow", _shallow_research)
    graph.add_node("deep_plan", _plan_deep)
    graph.add_node("deep_search", _deep_search)
    graph.add_node("deep_write", _write_deep)
    graph.set_entry_point("orchestrate")
    graph.add_conditional_edges("orchestrate", _route, {
        "shallow": "shallow",
        "deep_plan": "deep_plan",
    })
    graph.add_edge("shallow", END)
    graph.add_edge("deep_plan", "deep_search")
    graph.add_edge("deep_search", "deep_write")
    graph.add_edge("deep_write", END)
    return graph.compile()


_GRAPH = None


def research(query: str, mode: str = "search") -> str:
    global _GRAPH
    query = str(query or "").strip()
    if not query:
        raise ValueError("Informe o que devo pesquisar.")
    if _GRAPH is None:
        _GRAPH = _build_graph()
    result = _GRAPH.invoke({"query": query, "mode": mode})
    answer = str(result.get("answer") or "").strip()
    if not answer:
        raise RuntimeError("O fluxo de pesquisa terminou sem produzir uma resposta.")
    return answer


def search_sources(query: str, limit: int = 5) -> list[dict]:
    """Structured, bounded source lookup for background monitoring and internal tools."""
    return _tavily_search(query, deep=False, limit=limit)
