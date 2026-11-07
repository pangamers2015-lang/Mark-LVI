from __future__ import annotations

import httpx

from ion import config
from ion.orchestration.limiter import SlidingWindowRateLimiter

# All NVIDIA calls in this Python process share this exact limiter.
NVIDIA_LIMITER = SlidingWindowRateLimiter(config.nvidia_requests_per_minute(), 60.0)


class NvidiaProvider:
    name = "nvidia"

    def __init__(self) -> None:
        self.api_key = config.api_key("nvidia")
        self.model = config.model("nvidia")
        self.base_url = config.setting("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
        self.timeout = config.request_timeout()

    async def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_key:
            raise RuntimeError("Chave da NVIDIA ausente. Configure NVIDIA_API_KEY no arquivo .env.")
        await NVIDIA_LIMITER.acquire()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 16000,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=body,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"NVIDIA HTTP {response.status_code}: {response.text[:1200]}")
            payload = response.json()
        choices = payload.get("choices") or []
        text = (((choices[0].get("message") or {}).get("content")) if choices else "") or ""
        if not str(text).strip():
            raise RuntimeError("NVIDIA retornou resposta vazia.")
        return str(text).strip()

    async def health(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "NVIDIA_API_KEY não configurada."
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            return response.is_success, f"NVIDIA HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            return False, f"NVIDIA indisponível: {exc}"
