"""Discover and remember applications installed on this Windows computer.

Uses Windows uninstall registry entries, Start Menu shortcuts and the Windows
default-browser association. The inventory is local metadata; it never uploads
a machine-wide file listing or reads application data.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

BASE_DIR = Path(__file__).resolve().parent.parent
INVENTORY_PATH = BASE_DIR / "data" / "installed_apps.json"

_BROWSER_HINTS = {
    "edge": ("microsoft edge", "edge"),
    "chrome": ("google chrome", "chrome"),
    "firefox": ("mozilla firefox", "firefox"),
    "brave": ("brave",),
    "opera": ("opera",),
    "vivaldi": ("vivaldi",),
}
_CATEGORY_HINTS = {
    "browser": ("browser", "navegador", "chrome", "edge", "firefox", "opera", "brave", "vivaldi"),
    "development": ("visual studio", "vscode", "vs code", "python", "git", "node.js", "docker", "postman"),
    "communication": ("discord", "whatsapp", "telegram", "zoom", "teams", "slack", "skype"),
    "media": ("vlc", "spotify", "obs studio", "audacity", "capcut", "obs"),
    "gaming": ("steam", "epic games", "riot", "battle.net", "ubisoft", "ea app"),
    "office": ("microsoft 365", "office", "word", "excel", "powerpoint", "libreoffice"),
    "security": ("defender", "antivirus", "avast", "avg", "bitdefender", "malwarebytes"),
}


def _category(name: str) -> str:
    folded = name.casefold()
    for category, hints in _CATEGORY_HINTS.items():
        if any(hint in folded for hint in hints):
            return category
    return "other"


def _registry_apps() -> list[dict]:
    if winreg is None:
        return []
    found = {}
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, key_path in locations:
        try:
            with winreg.OpenKey(hive, key_path) as root:
                count = winreg.QueryInfoKey(root)[0]
                for index in range(count):
                    try:
                        sub = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, sub) as item:
                            name = winreg.QueryValueEx(item, "DisplayName")[0]
                            try:
                                location = winreg.QueryValueEx(item, "InstallLocation")[0]
                            except OSError:
                                location = ""
                            try:
                                publisher = winreg.QueryValueEx(item, "Publisher")[0]
                            except OSError:
                                publisher = ""
                            try:
                                command = winreg.QueryValueEx(item, "DisplayIcon")[0]
                            except OSError:
                                command = ""
                        name = str(name).strip()
                        if name:
                            key = name.casefold()
                            found[key] = {
                                "name": name, "category": _category(name),
                                "publisher": str(publisher), "install_location": str(location),
                                "executable_hint": str(command).split(",")[0].strip('"'),
                                "source": "windows_registry",
                            }
                    except (OSError, ValueError, TypeError):
                        continue
        except OSError:
            continue
    return list(found.values())


def _start_menu_apps() -> list[dict]:
    roots = (
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    )
    found = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for shortcut in root.rglob("*.lnk"):
                if len(found) >= 1000:
                    break
                name = shortcut.stem.strip()
                if name and not name.startswith(("Uninstall", "Readme")):
                    found.setdefault(name.casefold(), {
                        "name": name, "category": _category(name),
                        "publisher": "", "install_location": "",
                        "executable_hint": str(shortcut), "source": "start_menu_shortcut",
                    })
        except OSError:
            continue
    return list(found.values())


def _default_browser() -> str | None:
    if platform.system() != "Windows" or winreg is None:
        return None
    try:
        key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            prog_id = str(winreg.QueryValueEx(key, "ProgId")[0]).casefold()
        if "edge" in prog_id:
            return "edge"
        if "chrome" in prog_id:
            return "chrome"
        if "firefox" in prog_id:
            return "firefox"
        if "brave" in prog_id:
            return "brave"
        if "opera" in prog_id:
            return "opera"
        if "vivaldi" in prog_id:
            return "vivaldi"
    except OSError:
        pass
    return None


def scan() -> dict:
    if platform.system() != "Windows":
        return {"ok": False, "error": "The installed-app scanner currently supports Windows only."}
    apps = _registry_apps()
    by_name = {a["name"].casefold(): a for a in apps}
    for app in _start_menu_apps():
        by_name.setdefault(app["name"].casefold(), app)
    ordered = sorted(by_name.values(), key=lambda a: a["name"].casefold())
    browsers = []
    for app in ordered:
        name = app["name"].casefold()
        if "webview" not in name and any(any(hint in name for hint in hints) for hints in _BROWSER_HINTS.values()):
            browser = next((key for key, hints in _BROWSER_HINTS.items()
                            if any(hint in name for hint in hints)), None)
            if browser and browser not in browsers:
                browsers.append(browser)
    result = {
        "ok": True, "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "platform": platform.platform(), "count": len(ordered), "apps": ordered,
        "browsers": browsers, "default_browser": _default_browser(),
    }
    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = INVENTORY_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, INVENTORY_PATH)
    return result


def _load() -> dict:
    try:
        data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def app_inventory(parameters: dict = None, player=None) -> str:
    p = parameters or {}
    action = str(p.get("action") or "list").strip().lower()
    data = scan() if action == "scan" else _load()
    if action == "scan" and not data.get("ok"):
        return data.get("error", "Application scan failed.")
    if action == "browser":
        if not data.get("apps"):
            return "No saved inventory. Run action='scan' first."
        return json.dumps({
            "installed_browsers": data.get("browsers", []),
            "default_browser": data.get("default_browser"),
            "recommendation": data.get("default_browser") or (data.get("browsers") or [None])[0],
        }, ensure_ascii=False)
    if not data:
        return "No saved application inventory. Run action='scan' to inspect installed programs."
    query = str(p.get("query") or "").strip().casefold()
    apps = data.get("apps", [])
    if action == "find":
        apps = [a for a in apps if query in a.get("name", "").casefold()
                or query in a.get("category", "").casefold()]
    elif action == "category":
        category = query or "other"
        apps = [a for a in apps if a.get("category") == category]
    elif action not in ("list", "scan"):
        return "Supported actions: scan, list, find, category, browser."
    limit = max(1, min(int(p.get("limit") or 100), 250))
    lines = [f"Application inventory: {len(data.get('apps', []))} entries; "
             f"default browser: {data.get('default_browser') or 'not identified'}."]
    lines.extend(f"- {a['name']} | {a.get('category', 'other')} | {a.get('source', '')}"
                 for a in apps[:limit])
    if len(apps) > limit:
        lines.append(f"... and {len(apps) - limit} more.")
    return "\n".join(lines)


TOOL = {
    "name": "app_inventory",
    "description": (
        "Inspects the real Windows installed-app list and Start Menu shortcuts, "
        "categorizes applications, and identifies installed browsers and the "
        "Windows default browser. Use action='scan' when inventory is missing or "
        "stale, 'list' for the saved list, 'find' for a named program, "
        "'category' for a category, and 'browser' to resolve which browser to use. "
        "When opening a website, use the identified browser with browser_control; "
        "for background websites pass background=true. The scan is local and "
        "does not read app data or credentials."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "scan | list | find | category | browser"},
            "query": {"type": "STRING", "description": "Optional app name or category for find/category."},
            "limit": {"type": "INTEGER", "description": "Maximum rows to return, 1-250."}
        },
        "required": ["action"]
    },
    "tier": "core",
    "brief": "Scan and classify installed Windows apps; identify the default browser.",
    "handler": app_inventory,
}
