"""测试用 LLM 存根：按序返回预设响应，永不真调 oMLX。"""


class FakeLLM:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls += 1
        self.prompts.append((system, user))
        if not self._responses:
            return ""
        return self._responses.pop(0)

    async def stream(self, system: str, user: str):
        text = await self.complete(system, user)
        for ch in text:
            yield ch
