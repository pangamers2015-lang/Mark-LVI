# -*- coding: utf-8 -*-
"""Desktop HTML interface for Yon.

The visual layer is HTML/CSS/JavaScript in web/index.html. Python remains the
application backend and exposes a small localhost event/API bridge.
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
API_FILE = BASE_DIR / "config" / "api_keys.json"


class _EventHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = []
        self._last_state = {"tipo": "estado", "estado": "iniciando"}

    def emit(self, event):
        if event.get("tipo") == "estado":
            self._last_state = event
        with self._lock:
            for q in list(self._clients):
                try:
                    q.put_nowait(event)
                except Exception:
                    pass

    def subscribe(self):
        import queue
        q = queue.Queue()
        with self._lock:
            self._clients.append(q)
            q.put(self._last_state)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)


_EVENTS = _EventHub()


def _state_name(value):
    s = str(value or "").upper()
    if any(x in s for x in ("SPEAK", "TALK", "OUTPUT")):
        return "falando"
    if any(x in s for x in ("THINK", "PROCESS", "WORK", "TOOL")):
        return "pensando"
    if any(x in s for x in ("TRANSCR", "UNDERSTAND")):
        return "transcrevendo"
    if any(x in s for x in ("LISTEN", "RECORD", "MIC")):
        return "ouvindo"
    if any(x in s for x in ("INIT", "CONNECT", "WARM")):
        return "aquecendo"
    return "parado"


class _WindowShim:
    def __init__(self, ready):
        self._ready = bool(ready)
        self._assistant_name = "YON"
        self._muted = False


class _RootShim:
    def __init__(self, owner):
        self.owner = owner

    def mainloop(self):
        self.owner._run_window()

    def after(self, milliseconds, callback):
        timer = threading.Timer(max(0, milliseconds) / 1000.0, callback)
        timer.daemon = True
        timer.start()
        return timer

    def quit(self):
        try:
            if self.owner._window:
                self.owner._window.destroy()
        except Exception:
            pass

    def protocol(self, *_):
        return None


class _Handler(BaseHTTPRequestHandler):
    server_version = "YonWeb/1.0"

    def log_message(self, *_):
        return

    @property
    def ui(self):
        return self.server.ui

    def _send(self, code, body=b"", content_type="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8_000_000)
            return json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/eventos":
            return self._events()
        if path == "/api/config":
            return self._send(200, json.dumps({"voz": "", "velocidade": 1.0, "vozes": []}, ensure_ascii=False))
        if path == "/api/setup/status":
            return self._send(200, json.dumps({"ready": self.ui._win._ready}))
        if path == "/api/saude":
            return self._send(200, json.dumps({"app": "Yon", "ready": self.ui._win._ready, "clients": len(_EVENTS._clients)}))
        if path == "/api/overview":
            return self._send(200, json.dumps(self.ui._overview(), ensure_ascii=False))
        if path.startswith("/api/"):
            return self._send(404, "{}")
        rel = "index.html" if path in ("", "/") else unquote(path.lstrip("/"))
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
            return self._send(403, "{}")
        if not target.is_file():
            return self._send(404, "{}")
        kind = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if kind.startswith("text/") or kind in ("application/javascript", "image/svg+xml"):
            kind += "; charset=utf-8"
        return self._send(200, target.read_bytes(), kind)

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._json()
        if path == "/api/texto":
            text = str(data.get("texto", "")).strip()
            if text and self.ui.on_text_command:
                threading.Thread(target=self.ui.on_text_command, args=(text,), daemon=True).start()
                return self._send(202, '{"ok":true}')
            return self._send(409, '{"ok":false,"error":"Comando indisponível."}')
        if path == "/api/interromper":
            cb = self.ui.on_interrupt
            if cb:
                threading.Thread(target=cb, daemon=True).start()
            return self._send(200, '{"ok":true}')
        if path == "/api/ptt":
            held = bool(data.get("held"))
            if held and not self.ui._ptt_armed and self.ui.on_push_to_talk:
                try:
                    self.ui.on_push_to_talk(True)
                    self.ui._ptt_armed = True
                except Exception as exc:
                    return self._send(500, json.dumps({"error": str(exc)}))
            if self.ui.ptt_hold:
                threading.Thread(target=self.ui.ptt_hold, args=(held,), daemon=True).start()
                return self._send(200, '{"ok":true}')
            return self._send(503, '{"ok":false,"error":"Push-to-talk não está disponível."}')
        if path == "/api/reiniciar":
            self.ui.set_state("LISTENING")
            self.ui.write_log("SYS: Nova interação iniciada pela interface.")
            return self._send(200, '{"ok":true}')
        if path == "/api/config":
            if data.get("voz") and self.ui.on_voice_change:
                threading.Thread(target=self.ui.on_voice_change, daemon=True).start()
            return self._send(200, json.dumps({"voz": "", "velocidade": 1.0, "vozes": []}))
        if path == "/api/diag":
            self.ui.write_log("UI: " + str(data.get("evento", ""))[:80] + " " + str(data.get("detalhe", ""))[:180])
            return self._send(200, '{"ok":true}')
        if path == "/api/confirmacao":
            answer = "sim" if data.get("aceita") else "não"
            if self.ui.on_text_command:
                threading.Thread(target=self.ui.on_text_command, args=(answer,), daemon=True).start()
            self.ui.hide_confirm()
            return self._send(200, '{"ok":true}')
        if path == "/api/setup":
            key = str(data.get("key", "")).strip()
            os_name = str(data.get("os", "windows")).strip().lower()
            if not key or os_name not in ("windows", "macos", "linux"):
                return self._send(400, json.dumps({"error": "Chave ou sistema operacional inválido."}))
            try:
                API_FILE.parent.mkdir(parents=True, exist_ok=True)
                try:
                    current = json.loads(API_FILE.read_text(encoding="utf-8"))
                    if not isinstance(current, dict):
                        current = {}
                except Exception:
                    current = {}
                current["gemini_api_key"] = key
                current["os_system"] = os_name
                temp = API_FILE.with_suffix(".json.tmp")
                temp.write_text(json.dumps(current, ensure_ascii=False, indent=4), encoding="utf-8")
                os.replace(temp, API_FILE)
                self.ui._win._ready = True
                self.ui.set_state("LISTENING")
                self.ui.write_log("SYS: Configuração inicial concluída.")
                return self._send(200, '{"ok":true}')
            except Exception as exc:
                return self._send(500, json.dumps({"error": str(exc)}))
        if path == "/api/wake":
            try:
                action = data.get("action")
                if action == "toggle" and self.ui.on_wake_toggle:
                    result = self.ui.on_wake_toggle(bool(data.get("enabled")))
                elif action == "manual" and self.ui.on_wake_manual:
                    result = self.ui.on_wake_manual()
                elif action == "install" and self.ui.on_wake_install:
                    result = self.ui.on_wake_install()
                else:
                    result = self.ui.wake_get_state() if self.ui.wake_get_state else {}
                return self._send(200, json.dumps({"result": result}, ensure_ascii=False, default=str))
            except Exception as exc:
                return self._send(500, json.dumps({"error": str(exc)}))
        if path == "/api/action":
            action = data.get("action")
            if action == "plugins":
                return self._send(200, json.dumps({"items": self.ui.get_plugins() if self.ui.get_plugins else []}, ensure_ascii=False, default=str))
            if action == "tasks":
                return self._send(200, json.dumps({"items": self.ui.get_background_tasks() if self.ui.get_background_tasks else []}, ensure_ascii=False, default=str))
            if action == "plugin_settings":
                return self._send(200, json.dumps({"items": self.ui.get_plugin_settings() if self.ui.get_plugin_settings else []}, ensure_ascii=False, default=str))
            return self._send(400, '{"error":"Ação desconhecida."}')
        return self._send(404, "{}")

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q = _EVENTS.subscribe()
        try:
            while True:
                try:
                    item = q.get(timeout=15)
                    payload = "data: " + json.dumps(item, ensure_ascii=False, default=str) + "\n\n"
                except Exception:
                    payload = ": ping\n\n"
                self.wfile.write(payload.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            _EVENTS.unsubscribe(q)


class JarvisUI:
    """Compatibility surface for the existing Yon backend; UI is now HTML."""
    def __init__(self, face_path=None, size=None):
        self._ready = self._check_config()
        self._win = _WindowShim(self._ready)
        self.root = _RootShim(self)
        self._window = None
        self._server = None
        self._server_thread = None
        self._ptt_armed = False
        self._muted = False
        self._current_file = None
        self.on_text_command = None
        self.on_remote_clicked = None
        self.on_interrupt = None
        self.on_voice_change = None
        self.on_audio_device_change = None
        self.on_wake_toggle = None
        self.on_wake_manual = None
        self.on_wake_install = None
        self.wake_get_state = None
        self.wake_is_ready = None
        self.on_push_to_talk = None
        self.ptt_hold = None
        self.get_plugins = None
        self.get_plugin_settings = None
        self.get_background_tasks = None
        self.request_say = None
        self.defer_restart_until_idle = None
        self._assistant_name = "YON"

    def _check_config(self):
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    @property
    def muted(self):
        return self._muted

    @muted.setter
    def muted(self, value):
        self._muted = bool(value)
        _EVENTS.emit({"tipo": "aviso", "texto": "Microfone " + ("silenciado" if self._muted else "ativado") + "."})

    @property
    def current_file(self):
        return self._current_file

    @property
    def assistant_name(self):
        try:
            cfg = json.loads(API_FILE.read_text(encoding="utf-8"))
            return str(cfg.get("assistant_name") or "YON")
        except Exception:
            return "YON"

    def _run_window(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.ui = self
        self._server.daemon_threads = True
        port = self._server.server_address[1]
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="Yon-Web-Server")
        self._server_thread.start()
        url = f"http://127.0.0.1:{port}/"
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("A interface web precisa do pywebview. Execute: pip install pywebview") from exc
        self._window = webview.create_window("Yon", url, width=1280, height=800, min_size=(900, 560), background_color="#000000")
        webview.start(gui="edgechromium", debug=False)
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception:
            pass

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.2)

    def set_state(self, state):
        _EVENTS.emit({"tipo": "estado", "estado": _state_name(state)})

    def write_log(self, message):
        msg = str(message or "")[:1000]
        if msg.startswith("ERR:") or msg.startswith("WARN:"):
            _EVENTS.emit({"tipo": "aviso", "texto": msg})
        else:
            _EVENTS.emit({"tipo": "aviso", "texto": msg})

    def show_content(self, title, text):
        _EVENTS.emit({"tipo": "conteudo", "titulo": str(title or "")[:100], "texto": str(text or "")[:12000]})

    def show_code_job(self, job):
        _EVENTS.emit({"tipo": "codigo", "job": dict(job or {})})

    def show_quiz(self, topic, questions, grade=None):
        _EVENTS.emit({"tipo": "quiz", "topico": str(topic or ""), "questions": list(questions or [])})

    def hide_quiz(self):
        _EVENTS.emit({"tipo": "aviso", "texto": "Questionário encerrado."})

    def show_review(self, title, summary, findings, unclear=None):
        _EVENTS.emit({"tipo": "review", "titulo": str(title or ""), "resumo": str(summary or ""), "findings": list(findings or []), "unclear": list(unclear or [])})

    def show_confirm(self, title, detail):
        _EVENTS.emit({"tipo": "confirmacao", "titulo": str(title or "")[:120], "detalhe": str(detail or "")[:500]})

    def hide_confirm(self):
        _EVENTS.emit({"tipo": "aviso", "texto": "Confirmação encerrada."})

    def prompt_reconfig(self):
        self._win._ready = False
        _EVENTS.emit({"tipo": "setup", "show": True})

    def show_camera_frame(self, img_bytes):
        import base64
        _EVENTS.emit({"tipo": "camera", "data": base64.b64encode(img_bytes).decode("ascii")})

    def show_video(self, source, title="", muted=True, audio_source=""):
        _EVENTS.emit({"tipo": "video", "source": str(source or ""), "titulo": str(title or ""), "muted": bool(muted), "audio_source": str(audio_source or "")})

    def stop_video(self):
        _EVENTS.emit({"tipo": "video", "close": True})

    def set_video_muted(self, muted):
        _EVENTS.emit({"tipo": "aviso", "texto": "Áudio do vídeo " + ("silenciado." if muted else "ativado.")})

    def video_is_playing(self):
        return False

    def start_camera_stream(self):
        _EVENTS.emit({"tipo": "camera", "start": True})

    def stop_camera_stream(self):
        _EVENTS.emit({"tipo": "camera", "start": False})

    def notify_phone_connected(self):
        _EVENTS.emit({"tipo": "aviso", "texto": "Dispositivo móvel conectado."})

    def set_audio_level(self, level):
        _EVENTS.emit({"tipo": "nivel", "valor": max(0.0, min(1.0, float(level or 0.0)))})

    def push_visemes(self, frames, hop, at):
        try:
            level = max((float(f[0]) for f in frames), default=0.0)
            self.set_audio_level(level)
        except Exception:
            pass

    def glance(self, dx, dy, hold=1.1):
        _EVENTS.emit({"tipo": "glance", "dx": float(dx), "dy": float(dy), "hold": float(hold)})

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        self.set_state("LISTENING")

    def _overview(self):
        return {
            "assistant": self.assistant_name,
            "plugins": self.get_plugins() if self.get_plugins else [],
            "tasks": self.get_background_tasks() if self.get_background_tasks else [],
            "wake": self.wake_get_state() if self.wake_get_state else {},
        }
