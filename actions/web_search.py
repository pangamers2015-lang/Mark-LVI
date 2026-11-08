"""Jarvis native web-research action.

The public TOOL contract remains stable for the live action loader. Search and
research are implemented internally with LangGraph, Tavily, and NVIDIA Nemotron.
Open-Meteo remains a separate weather data API, not a second web-search engine.
"""
from core import outcome


def _weather(query: str) -> str:
    import re
    import requests

    place = re.sub(
        r"(?i)^(?:qual\s+(?:é\s+)?a\s+)?(?:previs[aã]o\s+do\s+tempo|"
        r"previs[aã]o|clima|tempo|weather(?:\s+forecast)?|forecast)"
        r"(?:\s+(?:para|em|de|da|do|for|in))?\s*", "", str(query or "")
    ).strip(" ,.-")
    if not place:
        raise ValueError("Informe a cidade para consultar a previsão do tempo.")
    parts = [part.strip() for part in place.split(",") if part.strip()]
    city = parts[0] if parts else place
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 5, "language": "pt", "format": "json"},
        timeout=12,
    )
    geo.raise_for_status()
    matches = geo.json().get("results") or []
    if not matches:
        raise ValueError(f"Não encontrei a localização '{city}'.")
    selected = matches[0]
    forecast = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": selected["latitude"], "longitude": selected["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 3, "timezone": "auto",
        },
        timeout=12,
    )
    forecast.raise_for_status()
    data = forecast.json()
    current, daily = data.get("current") or {}, data.get("daily") or {}
    location = ", ".join(str(x) for x in (
        selected.get("name"), selected.get("admin1"), selected.get("country")
    ) if x)
    lines = [
        f"Previsão do tempo — {location}",
        f"Agora: {current.get('temperature_2m', '—')} °C; sensação de "
        f"{current.get('apparent_temperature', '—')} °C; umidade "
        f"{current.get('relative_humidity_2m', '—')}%; vento "
        f"{current.get('wind_speed_10m', '—')} km/h.",
        "Próximos dias:",
    ]
    for i, date in enumerate((daily.get("time") or [])[:3]):
        lines.append(
            f"- {date}: mínima {daily['temperature_2m_min'][i]} °C, "
            f"máxima {daily['temperature_2m_max'][i]} °C; chance de chuva "
            f"{daily['precipitation_probability_max'][i]}%."
        )
    lines.append("Fonte: Open-Meteo (https://open-meteo.com/).")
    return "\n".join(lines)


def _news(query: str = "") -> str:
    from actions.research_engine import research
    from datetime import datetime
    topic = query.strip() or "principais notícias atuais do Brasil e do mundo"
    return research(
        f"Notícias publicadas hoje ou nos últimos dias até {datetime.now().astimezone():%d/%m/%Y}: {topic}. "
        "Priorize fontes primárias, informe datas e diferencie data do evento da publicação.",
        mode="search",
    )


def web_search(parameters: dict, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = str(params.get("query") or "").strip()
    mode = str(params.get("mode") or "search").lower().strip()
    items = params.get("items") or []
    aspect = str(params.get("aspect") or "geral").strip() or "geral"
    if items and mode != "compare":
        mode = "compare"
    if not query and not items:
        return "Informe o que devo pesquisar."
    if mode == "compare":
        query = f"Compare {', '.join(map(str, items))} em relação a {aspect}. {query}".strip()
    elif mode == "news":
        query = f"Notícias recentes e verificáveis sobre {query or 'os principais acontecimentos'}."
    elif mode == "price":
        query = f"Preços atuais, disponibilidade e especificações de: {query}."
    if player:
        try:
            player.write_log(f"[Jarvis Research] {mode}: {query}")
        except Exception:
            pass
    try:
        if mode == "weather":
            found = _weather(query)
        else:
            from actions.research_engine import research
            found = research(query, mode="research" if mode in {"research", "deep"} else "search")
        if session_memory:
            try:
                session_memory.set_last_search(query=query, response=found)
            except Exception:
                pass
        return outcome.untrusted("web", found)
    except Exception as exc:
        message = f"Pesquisa do Jarvis falhou ({mode}): {exc}"
        if player:
            try:
                player.write_log(f"[Jarvis Research] {message}")
            except Exception:
                pass
        return outcome.failed("web_search", message, query=query)


TOOL = {
    "behavior": "NON_BLOCKING",
    "scheduling": "WHEN_IDLE",
    "name": "web_search",
    "description": (
        "Pesquisa nativa do Jarvis, sem delegar a FCC/Qwen/outros agentes. "
        "Usa LangGraph para orquestrar pesquisa rápida e profunda, Tavily como "
        "único mecanismo web e NVIDIA Nemotron para planejamento e síntese com "
        "citações. Modos: search (rápida), news, research (aprofundada), price, "
        "compare e weather (Open-Meteo). Requer NVIDIA_API_KEY e TAVILY_API_KEY "
        "ou as chaves nvidia_api_key e tavily_api_key em config/api_keys.json."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Consulta ou assunto"},
            "mode": {"type": "STRING", "description": "search | news | research | price | compare | weather"},
            "items": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Itens a comparar"},
            "aspect": {"type": "STRING", "description": "Critério de comparação"},
        },
        "required": ["query"],
    },
    "handler": web_search,
}
