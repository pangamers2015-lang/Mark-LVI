# Open-WebSearch is the only web-search provider used by Yon.
# It runs as a local HTTP daemon; no Tavily, Gemini grounding, or DDGS fallback.
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from core import outcome


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
PORT = int(os.environ.get("OPEN_WEBSEARCH_PORT", "3210"))
BASE_URL = f"http://127.0.0.1:{PORT}"
ENGINES = ["bing", "duckduckgo", "startpage", "exa", "brave", "hackernews"]
_START_LOCK = threading.Lock()
_DAEMON = None


def _log(message: str) -> None:
    try:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "open_websearch.log").open("a", encoding="utf-8") as stream:
            stream.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except OSError:
        print(f"[OpenWebSearch] {message}")


def _health(timeout: float = 1.5) -> bool:
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=timeout)
        return response.ok and response.json().get("status") == "ok"
    except (requests.RequestException, ValueError):
        return False


def _start_daemon() -> None:
    """Start the official local daemon on demand; npx installs it in npm's cache."""
    global _DAEMON
    if _health():
        return
    with _START_LOCK:
        if _health():
            return
        npx = shutil.which("npx.cmd") or shutil.which("npx")
        if not npx:
            raise RuntimeError(
                "Node.js/npm não foi encontrado. Instale o Node.js LTS e reinicie o Yon."
            )
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_stream = (log_dir / "open_websearch.log").open("a", encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "MODE": "http",
            "PORT": str(PORT),
            "DEFAULT_SEARCH_ENGINE": "bing",
            "ALLOWED_SEARCH_ENGINES": ",".join(ENGINES),
            "SEARCH_MODE": "auto",
        })
        command = [npx, "--yes", "open-websearch@latest", "serve", "--port", str(PORT)]
        try:
            if os.name == "nt" and npx.lower().endswith((".cmd", ".bat")):
                command_line = subprocess.list2cmdline(command)
                _DAEMON = subprocess.Popen(
                    command_line, cwd=str(BASE_DIR), env=env, stdout=log_stream,
                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, shell=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                _DAEMON = subprocess.Popen(
                    command, cwd=str(BASE_DIR), env=env, stdout=log_stream,
                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if os.name == "nt" else 0,
                )
        except Exception:
            log_stream.close()
            raise
        # The daemon inherits this file handle. Do not close it here.
        _log(f"Starting open-websearch daemon on {BASE_URL}")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if _health():
                _log("Open-WebSearch daemon is ready.")
                return
            if _DAEMON.poll() is not None:
                raise RuntimeError(
                    "Open-WebSearch encerrou durante a inicialização. "
                    f"Consulte {log_dir / 'open_websearch.log'}."
                )
            time.sleep(0.5)
        raise TimeoutError(
            "Open-WebSearch não respondeu em 45 segundos. "
            f"Consulte {log_dir / 'open_websearch.log'}."
        )


def _search_open_websearch(query: str, limit: int = 8) -> str:
    _start_daemon()
    response = requests.post(
        f"{BASE_URL}/search",
        json={"query": query, "limit": max(1, min(int(limit), 20)),
              "engines": ENGINES, "searchMode": "auto"},
        timeout=(5, 45),
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        detail = payload.get("error") or payload.get("hint") or "resposta inválida"
        raise RuntimeError(f"Open-WebSearch: {detail}")
    data = payload.get("data")
    if isinstance(data, dict):
        results = data.get("results") or data.get("items") or []
    elif isinstance(data, list):
        results = data
    else:
        results = payload.get("results") or []
    if not results:
        raise RuntimeError("Open-WebSearch não encontrou resultados para essa consulta.")
    lines = [f"Resultados do Open-WebSearch para: {query}", "", "Fontes:"]
    seen = set()
    for index, item in enumerate(results, 1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or item.get("link") or "").strip()
        snippet = str(item.get("description") or item.get("snippet") or "").strip()
        engine = str(item.get("engine") or item.get("source") or "").strip()
        key = url or title
        if not key or key in seen:
            continue
        seen.add(key)
        if title:
            lines.append(f"{len(seen)}. {title}")
        if snippet:
            lines.append(f"   {snippet[:1600]}")
        if engine:
            lines.append(f"   Mecanismo: {engine}")
        if url:
            lines.append(f"   Fonte: {url}")
    if not seen:
        raise RuntimeError("Open-WebSearch retornou dados sem fontes utilizáveis.")
    return "\n".join(lines)


# Weather remains a separate, free public-data API; it is not a search provider.
_WMO_PT = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado",
    3: "nublado", 45: "neblina", 48: "neblina com geada",
    51: "garoa leve", 53: "garoa moderada", 55: "garoa intensa",
    56: "garoa congelante leve", 57: "garoa congelante intensa",
    61: "chuva leve", 63: "chuva moderada", 65: "chuva forte",
    66: "chuva congelante leve", 67: "chuva congelante forte",
    71: "neve leve", 73: "neve moderada", 75: "neve forte",
    77: "grãos de neve", 80: "pancadas de chuva leves",
    81: "pancadas de chuva moderadas", 82: "pancadas de chuva fortes",
    85: "pancadas de neve leves", 86: "pancadas de neve fortes",
    95: "trovoadas", 96: "trovoadas com granizo leve",
    99: "trovoadas com granizo forte",
}


def _weather(query: str) -> str:
    import re

    place = re.sub(
        r"(?i)^(?:qual\s+(?:é\s+)?a\s+)?(?:previs[aã]o\s+do\s+tempo|"
        r"previs[aã]o|clima|tempo|weather(?:\s+forecast)?|forecast)"
        r"(?:\s+(?:para|em|de|da|do|for|in))?\s*",
        "", str(query or "")
    ).strip(" ,.-")
    if not place:
        raise ValueError("Informe a cidade para consultar a previsão do tempo.")
    place = re.sub(r"(?i)^(?:cidade\s+de|city\s+of)\s+", "", place)
    parts = [part.strip() for part in place.split(",") if part.strip()]
    city = parts[0] if parts else place
    state_hint = parts[1].lower() if len(parts) > 1 else ""
    state_hint = {"sc": "santa catarina"}.get(state_hint, state_hint)
    country_hint = "BR" if any(
        term in place.lower() for term in ("brasil", "brazil", "sc", "santa catarina")
    ) else None
    geo_params = {"name": city, "count": 8, "language": "pt", "format": "json"}
    if country_hint:
        geo_params["countryCode"] = country_hint
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params=geo_params, timeout=12,
    )
    geo.raise_for_status()
    matches = geo.json().get("results") or []
    if not matches:
        raise ValueError(f"Não encontrei a localização '{city}'.")
    selected = matches[0]
    if state_hint:
        for candidate in matches:
            admin = str(candidate.get("admin1") or "").lower()
            if state_hint in admin or admin in state_hint:
                selected = candidate
                break
    forecast = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": selected["latitude"], "longitude": selected["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
            "forecast_days": 3, "timezone": "auto",
            "temperature_unit": "celsius", "wind_speed_unit": "kmh",
        },
        timeout=12,
    )
    forecast.raise_for_status()
    data = forecast.json()
    current, daily = data.get("current") or {}, data.get("daily") or {}
    location = ", ".join(str(v) for v in (
        selected.get("name"), selected.get("admin1"), selected.get("country")
    ) if v)
    code = int(current.get("weather_code", -1))
    lines = [
        f"Previsão do tempo — {location}",
        f"Agora ({current.get('time', 'horário local')}): {_WMO_PT.get(code, 'condição não informada')}, "
        f"{current.get('temperature_2m', '—')} °C; sensação de {current.get('apparent_temperature', '—')} °C.",
        f"Umidade: {current.get('relative_humidity_2m', '—')}%. "
        f"Vento: {current.get('wind_speed_10m', '—')} km/h. "
        f"Precipitação atual: {current.get('precipitation', '—')} mm.",
        "Próximos dias:",
    ]
    for i, date in enumerate((daily.get("time") or [])[:3]):
        lines.append(
            f"- {date}: {_WMO_PT.get(int(daily['weather_code'][i]), 'condição variável')}; "
            f"mínima {daily['temperature_2m_min'][i]} °C, "
            f"máxima {daily['temperature_2m_max'][i]} °C; "
            f"chance máxima de chuva {daily['precipitation_probability_max'][i]}%; "
            f"precipitação prevista {daily['precipitation_sum'][i]} mm."
        )
    lines.append("Fonte: Open-Meteo (https://open-meteo.com/).")
    return "\n".join(lines)


def _news(query: str = "") -> str:
    topic = query.strip() or "principais notícias atuais do Brasil e do mundo"
    return _search_open_websearch(f"Notícias recentes e atualizadas: {topic}", limit=8)


def _search(query: str) -> str:
    return _search_open_websearch(query, limit=8)


def _research(query: str) -> str:
    prompt = (
        f"Faça uma pesquisa aprofundada sobre: {query}. "
        "Priorize fontes primárias, dados verificáveis, contexto e datas. "
        "Retorne fontes e URLs."
    )
    return _search_open_websearch(prompt, limit=15)


def _price(query: str) -> str:
    return _search_open_websearch(
        f"Preço atual, disponibilidade e lojas para: {query}", limit=10
    )


def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} em relação a {aspect}. "
        "Use especificações, números e fontes verificáveis."
    )
    return _search_open_websearch(query, limit=12)


def web_search(parameters: dict, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = str(params.get("query") or "").strip()
    mode = str(params.get("mode") or "search").lower().strip()
    items = params.get("items") or []
    aspect = str(params.get("aspect") or "geral").strip() or "geral"
    if not query and not items:
        return "Informe o que devo pesquisar."
    if items and mode != "compare":
        mode = "compare"
    if player:
        try:
            player.write_log(f"[Open-WebSearch] {mode}: {query or ', '.join(items)}")
        except Exception:
            pass
    try:
        if mode == "weather":
            found = _weather(query)
        elif mode == "news":
            found = _news(query)
        elif mode == "research":
            found = _research(query)
        elif mode == "price":
            found = _price(query)
        elif mode == "compare":
            found = _compare(items, aspect)
        else:
            found = _search(query)
        return outcome.untrusted("web", found)
    except Exception as exc:
        _log(f"Search failed ({mode}): {exc}")
        return outcome.failed("web_search", f"Open-WebSearch falhou: {exc}",
                              query=query or ", ".join(items))


TOOL = {
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "name": "web_search",
    "description": (
        "Pesquisa a internet usando exclusivamente o Open-WebSearch, executado "
        "como daemon HTTP local. O serviço consulta vários mecanismos (Bing, "
        "DuckDuckGo, Startpage, Exa, Brave e Hacker News) e retorna títulos, "
        "trechos, URLs e mecanismo de origem. Não use conhecimento interno para "
        "responder fatos atuais: pesquise e cite as fontes. Modos: search, news, "
        "research, price, compare e weather. Weather usa Open-Meteo diretamente, "
        "sem chave. Se o daemon não estiver instalado, tenta iniciá-lo via npx; "
        "requer Node.js/npm."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Consulta ou assunto"},
            "mode": {"type": "STRING", "description": "search | news | research | price | compare | weather"},
            "items": {"type": "ARRAY", "items": {"type": "STRING"},
                      "description": "Itens a comparar"},
            "aspect": {"type": "STRING", "description": "Critério de comparação"},
        },
        "required": ["query"],
    },
    "handler": web_search,
}
