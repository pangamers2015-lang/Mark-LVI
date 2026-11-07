from __future__ import annotations

import json
import os
import queue
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CONFIG = ROOT / "config" / "api_key.json"
HOST, PORT = "127.0.0.1", 8765
TEXT_MODEL = "gemini-2.5-flash"
MAX_BODY = 8 * 1024 * 1024
_clients: list[queue.Queue] = []
_clients_lock = threading.Lock()
_voice = None


def publish(event: dict):
    payload = dict(event)
    with _clients_lock:
        clients = list(_clients)
    for client in clients:
        try:
            client.put_nowait(payload)
        except queue.Full:
            try:
                client.get_nowait()
                client.put_nowait(payload)
            except queue.Empty:
                pass


def read_config() -> dict:
    try:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(key: str):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"api_key": key}, indent=2), encoding="utf-8")


def api_key() -> str:
    return str(read_config().get("api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()


def start_voice():
    global _voice
    if _voice is not None and _voice.running:
        return True
    key = api_key()
    if not key:
        raise RuntimeError("Configure a chave Gemini na engrenagem.")
    try:
        from voice_live import LiveVoice
        _voice = LiveVoice(key, publish)
        _voice.start()
        return True
    except ImportError as exc:
        raise RuntimeError(f"Dependências de voz ausentes. Instale requirements.txt. Detalhe: {exc}")


def ask_gemini(message: str, attachment: dict | None = None) -> str:
    key = api_key()
    if not key:
        raise RuntimeError("Configure a chave Gemini na engrenagem antes de conversar.")
    prompt = message.strip()
    if attachment and attachment.get("text"):
        name = str(attachment.get("name") or "arquivo")[:180]
        content = str(attachment["text"])[:1_000_000]
        prompt += f"\n\nConteúdo do arquivo anexado ({name}):\n{content}"
    payload = {
        "system_instruction": {"parts": [{"text": (
            "Você é Yon, um agente pessoal. Responda em português brasileiro por padrão, "
            "com naturalidade, clareza e concisão. Nesta versão inicial, converse e analise "
            "texto e anexos; ainda não execute ações no computador."
        )}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1200},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:700]
        raise RuntimeError(f"Gemini respondeu HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Não foi possível conectar ao Gemini: {exc}") from exc
    try:
        return "".join(p.get("text", "") for p in result["candidates"][0]["content"]["parts"]).strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("O Gemini não retornou uma resposta de texto válida.")


class Handler(BaseHTTPRequestHandler):
    server_version = "YonLocal/0.2"

    def log_message(self, *_):
        pass

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = min(int(self.headers.get("Content-Length", "0")), MAX_BODY)
        value = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        return value if isinstance(value, dict) else {}

    def do_GET(self):
        if self.path == "/api/config":
            self.send_json(200, {"configured": bool(api_key()), "voice_running": bool(_voice and _voice.running),
                                 "text_model": TEXT_MODEL, "live_model": "models/gemini-3.1-flash-live-preview"})
            return
        if self.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            client = queue.Queue(maxsize=100)
            with _clients_lock:
                _clients.append(client)
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        event = client.get(timeout=15)
                        data = json.dumps(event, ensure_ascii=False).encode("utf-8")
                        self.wfile.write(b"data: " + data + b"\n\n")
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with _clients_lock:
                    if client in _clients:
                        _clients.remove(client)
            return
        path = "/index.html" if self.path in ("", "/") else self.path.split("?", 1)[0]
        target = (WEB / path.lstrip("/")).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            data = self.read_json()
            if self.path == "/api/config":
                key = str(data.get("api_key") or "").strip()
                if key:
                    write_config(key)
                    try:
                        start_voice()
                    except Exception as exc:
                        publish({"type": "voice_error", "text": str(exc)})
                self.send_json(200, {"ok": True, "configured": bool(api_key())})
                return
            if self.path == "/api/voice/start":
                start_voice()
                self.send_json(200, {"ok": True})
                return
            if self.path == "/api/voice/stop":
                if _voice:
                    _voice.stop()
                self.send_json(200, {"ok": True})
                return
            if self.path == "/api/interrupt":
                if _voice:
                    _voice.interrupt()
                self.send_json(200, {"ok": True})
                return
            if self.path == "/api/chat":
                message = str(data.get("message") or "").strip()
                attachment = data.get("attachment")
                if attachment and attachment.get("text"):
                    message += f"\n\nArquivo {str(attachment.get('name') or 'anexado')}:\n{str(attachment['text'])[:1_000_000]}"
                if not message:
                    self.send_json(400, {"ok": False, "error": "Digite ou fale uma mensagem."})
                    return
                if _voice and _voice.connected:
                    _voice.send_text_now(message)
                    self.send_json(202, {"ok": True, "live": True})
                    return
                self.send_json(200, {"ok": True, "answer": ask_gemini(message)})
                return
            self.send_json(404, {"ok": False, "error": "Rota não encontrada."})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)[:1000]})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Yon interface: http://{HOST}:{PORT}")
    print("Pressione Ctrl+C para encerrar.")
    if api_key():
        try:
            start_voice()
        except Exception as exc:
            publish({"type": "voice_error", "text": str(exc)})
            print(f"[Voz] {exc}")
    import threading as _threading
    import webbrowser
    _threading.Timer(0.8, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando Yon...")
    finally:
        if _voice:
            _voice.stop()
        server.server_close()


if __name__ == "__main__":
    main()
