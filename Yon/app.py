from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CONFIG = ROOT / "config" / "api_key.json"
HOST, PORT = "127.0.0.1", 8765
MODEL = "gemini-2.5-flash"
MAX_BODY = 8 * 1024 * 1024


def read_config() -> dict:
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(data: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ask_gemini(message: str, attachment: dict | None = None) -> str:
    key = (read_config().get("api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()
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
            "com naturalidade, clareza e concisão. Ainda não execute ações no computador; "
            "nesta versão inicial, converse e analise texto e anexos."
        )}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1200}
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
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
    server_version = "YonLocal/0.1"

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
        if length <= 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        return value if isinstance(value, dict) else {}

    def do_GET(self):
        if self.path == "/api/config":
            cfg = read_config()
            self.send_json(200, {"configured": bool(cfg.get("api_key") or os.environ.get("GEMINI_API_KEY")),
                                 "model": MODEL})
            return
        path = "/index.html" if self.path in ("", "/") else self.path.split("?", 1)[0]
        target = (WEB / path.lstrip("/")).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            self.send_error(404)
            return
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "application/octet-stream"
        body = target.read_bytes()
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
                    write_config({"api_key": key})
                self.send_json(200, {"ok": True, "configured": bool(key or read_config().get("api_key"))})
                return
            if self.path == "/api/chat":
                message = str(data.get("message") or "").strip()
                if not message:
                    self.send_json(400, {"ok": False, "error": "Digite ou fale uma mensagem."})
                    return
                answer = ask_gemini(message, data.get("attachment"))
                self.send_json(200, {"ok": True, "answer": answer, "model": MODEL})
                return
            self.send_json(404, {"ok": False, "error": "Rota não encontrada."})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)[:1000]})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Yon interface: {url}")
    print("Pressione Ctrl+C para encerrar.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando Yon...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
