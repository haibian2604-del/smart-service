import json

import httpx

from app.core.config import get_settings


class OMLXClient:
    """oMLX 本地推理，OpenAI 兼容 /v1/chat/completions。"""

    def _headers(self) -> dict:
        s = get_settings()
        return {"Authorization": f"Bearer {s.llm_api_key}"} if s.llm_api_key != "none" else {}

    def _payload(self, system: str, user: str, *, stream: bool) -> dict:
        s = get_settings()
        return {
            "model": s.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "stream": stream,
        }

    async def complete(self, system: str, user: str) -> str:
        s = get_settings()
        async with httpx.AsyncClient(base_url=s.llm_base_url, timeout=60, headers=self._headers()) as client:
            resp = await client.post("/chat/completions", json=self._payload(system, user, stream=False))
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream(self, system: str, user: str, on_token) -> str:
        """流式生成：每个增量 token 调用 on_token（同步回调），返回完整文本。"""
        s = get_settings()
        parts: list[str] = []
        async with httpx.AsyncClient(base_url=s.llm_base_url, timeout=60, headers=self._headers()) as client:
            async with client.stream("POST", "/chat/completions",
                                     json=self._payload(system, user, stream=True)) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    delta = json.loads(payload)["choices"][0].get("delta", {}).get("content")
                    if delta:
                        parts.append(delta)
                        on_token(delta)
        return "".join(parts)


_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = OMLXClient()
    return _llm


def set_llm(llm) -> None:
    """测试注入用。"""
    global _llm
    _llm = llm
