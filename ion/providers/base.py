from __future__ import annotations

from typing import Protocol


class TextProvider(Protocol):
    name: str

    async def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> str:
        ...

    async def health(self) -> tuple[bool, str]:
        ...
