"""Weather action delegated to the single central Open-WebSearch service."""


def weather_action(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    city = params.get("city")
    when = str(params.get("time") or "today").strip()
    if not isinstance(city, str) or not city.strip():
        msg = "Informe a cidade para consultar a previsão do tempo."
        _log(msg, player)
        return msg

    from actions.web_search import _weather
    try:
        msg = _weather(f"previsão do tempo para {city.strip()}")
        _log(msg, player)
        if session_memory:
            try:
                session_memory.set_last_search(
                    query=f"previsão do tempo para {city.strip()}",
                    response=msg,
                )
            except Exception:
                pass
        return msg
    except Exception as exc:
        msg = f"Não foi possível consultar a previsão do tempo: {exc}"
        _log(msg, player)
        return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass


TOOL = {
    "name": "weather_report",
    "description": "Consulta a previsão usando o serviço central Open-Meteo integrado ao Open-WebSearch.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {"type": "STRING", "description": "Nome da cidade"},
            "time": {"type": "STRING", "description": "Período desejado"},
        },
        "required": ["city"],
    },
    "handler": weather_action,
}
