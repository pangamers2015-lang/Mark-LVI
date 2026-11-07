from __future__ import annotations

import httpx

from ion import config


class GeminiProvider:
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self) -> None:
        self.api_key = config.api_key("gemini")
        self.model = config.model("gemini")
        self.timeout = config.request_timeout()

    async def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError("Chave da Gemini ausente. Configure GEMINI_API_KEY no arquivo .env.")
        url = f"{self.BASE_URL}/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 16000},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers={"x-goog-api-key": self.api_key}, json=body)
            if response.status_code >= 400:
                raise RuntimeError(f"Gemini HTTP {response.status_code}: {response.text[:1200]}")
            payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            feedback = payload.get("promptFeedback") or {}
            raise RuntimeError(f"Gemini não retornou conteúdo: {feedback or payload}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise RuntimeError("Gemini retornou resposta vazia.")
        return text.strip()

    async def health(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "GEMINI_API_KEY não configurada."
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, headers={"x-goog-api-key": self.api_key})
            return (response.is_success, f"Gemini HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            return False, f"Gemini indisponível: {exc}"
