from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from app.core.config import get_settings


class LLMClient(Protocol):
    async def complete(self, system: str, user: str) -> str: ...
    def stream(self, system: str, user: str) -> AsyncIterator[str]: ...


class OMLXClient:
    """oMLX 本地推理，OpenAI 兼容 /v1/chat/completions。"""

    async def complete(self, system: str, user: str) -> str:
        s = get_settings()
        async with httpx.AsyncClient(base_url=s.llm_base_url, timeout=60) as client:
            resp = await client.post("/chat/completions", json={
                "model": s.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
            })
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream(self, system: str, user: str) -> AsyncIterator[str]:
        # ponytail: 演示用非流式凑成逐字，真流式等 P5 接 SSE 时再上
        text = await self.complete(system, user)
        for ch in text:
            yield ch


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = OMLXClient()
    return _llm


def set_llm(llm: LLMClient) -> None:
    """测试注入用。"""
    global _llm
    _llm = llm
