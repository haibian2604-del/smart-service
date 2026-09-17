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



class SmartFakeLLM(FakeLLM):
    """API/端到端测试用：按关键词做意图分类并生成模板回复，与输入顺序无关。"""

    async def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if "intent" in system:
            if "退" in user:
                return '{"intent":"refund"}'
            if "订单" in user or "到哪" in user or "#A" in user:
                return '{"intent":"order"}'
            if any(k in user for k in ("耳机", "键盘", "帐篷", "水壶", "商品", "价格")):
                return '{"intent":"product"}'
            return '{"intent":"chitchat"}'
        if "商品列表" in user:
            return "为您找到以下商品。"
        if "订单信息" in user:
            return "这是您的订单信息。"
        return "好的。"
