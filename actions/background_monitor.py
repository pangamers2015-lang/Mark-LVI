"""
BackgroundMonitor — user-configured topic watching.
Uses the Jarvis native research provider (Tavily) once per day per topic.
No crypto, no finance, no uninvited tracking.
"""
import hashlib
import json
import re
from datetime import datetime


_BLOCKED = {
    "bitcoin", "ethereum", "dogecoin", "solana", "binance", "nft",
    "blockchain", "defi", "altcoin", "memecoin", "coin", "token",
    "crypto", "kripto", "cripto", "krypto", "крипто", "仮仮想通貨",
    "cryptocurrency",
}


def _is_blocked(topic: str) -> bool:
    return any(word in topic.lower() for word in _BLOCKED)


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic.lower().strip())[:40].strip("_")


def _title_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _load() -> dict:
    from memory.memory_manager import load_memory
    data = load_memory().get("monitors", {})
    return data if isinstance(data, dict) else {}


def _save(monitors: dict) -> None:
    from memory.memory_manager import load_memory, MEMORY_PATH, _lock
    memory = load_memory()
    memory["monitors"] = monitors
    with _lock:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def add_monitor(topic: str) -> str:
    topic = topic.strip()
    if not topic:
        return "Please specify a topic to monitor."
    if _is_blocked(topic):
        return "I don't monitor crypto or financial topics."
    monitors = _load()
    slug = _slug(topic)
    if slug in monitors:
        return f"Already monitoring: {monitors[slug]['topic']}"
    monitors[slug] = {"topic": topic, "added": datetime.now().strftime("%Y-%m-%d"),
                      "last_check": "", "last_hash": ""}
    _save(monitors)
    print(f"[Monitor] Added: {topic}")
    return f"Now monitoring: {topic}"


def remove_monitor(topic: str) -> str:
    topic = topic.strip().lower()
    monitors = _load()
    slug = _slug(topic)
    if slug in monitors:
        label = monitors.pop(slug)["topic"]
        _save(monitors)
        return f"Stopped monitoring: {label}"
    for key, val in list(monitors.items()):
        if topic in val.get("topic", "").lower():
            label = monitors.pop(key)["topic"]
            _save(monitors)
            return f"Stopped monitoring: {label}"
    return f"Not found in monitored topics: {topic}"


def list_monitors() -> list[str]:
    return [v.get("topic", k) for k, v in _load().items()]


def check_all() -> list[str]:
    """Check pending topics once per day and return [MONITOR_ALERT] strings."""
    from actions.research_engine import search_sources

    monitors = _load()
    if not monitors:
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    alerts, changed = [], False
    for slug, data in monitors.items():
        if data.get("last_check") == today:
            continue
        topic = data.get("topic", slug)
        try:
            results = search_sources(
                f"Notícias recentes sobre {topic}; priorize fontes atuais e informe datas",
                limit=5,
            )
            if not results:
                monitors[slug]["last_check"] = today
                changed = True
                continue
            top = results[0]
            title = str(top.get("title") or "").strip()
            if not title:
                continue
            digest = _title_hash(title)
            monitors[slug]["last_check"] = today
            changed = True
            if digest == data.get("last_hash"):
                continue
            monitors[slug]["last_hash"] = digest
            snippet = str(top.get("content") or "")[:150]
            source = str(top.get("url") or "")
            parts = [f"[MONITOR_ALERT] {topic}", f"Headline: {title}"]
            if snippet:
                parts.append(snippet)
            if source:
                parts.append(f"Source: {source}")
            alerts.append("\n".join(parts))
            print(f"[Monitor] New headline for '{topic}': {title[:60]}")
        except Exception as exc:
            print(f"[Monitor] Check failed for '{topic}': {exc}")
    if changed:
        _save(monitors)
    return alerts
