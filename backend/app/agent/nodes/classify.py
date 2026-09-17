from pydantic import BaseModel

from app.agent.llm_json import ask_json
from app.agent.prompts.classify import SYSTEM
from app.agent.slots import extract_order_no, extract_refund_amount
from app.agent.state import AgentState


INTENTS = ("product", "order", "refund", "chitchat", "unknown")


class IntentOutput(BaseModel):
    intent: str


# 关键词兜底：LLM 挂掉/输出不合法时保证 demo 不翻车
_KEYWORD_RULES = [
    ("refund", ("退款", "退货", "退了", "退掉")),
    ("order", ("订单", "物流", "到哪", "发货", "快递")),
    ("product", ("耳机", "键盘", "帐篷", "水壶", "商品", "有没有", "多少钱", "价格")),
]


def _keyword_intent(text: str) -> str:
    for intent, keywords in _KEYWORD_RULES:
        if any(k in text for k in keywords):
            return intent
    if any(k in text for k in ("你好", "您好", "嗨", "hello", "hi")):
        return "chitchat"
    return "unknown"


async def classify_node(state: AgentState, *, llm) -> dict:
    text = state["text"]
    # 跨轮记忆：把本轮之前的对话带给分类器，解决指代/省略型追问
    hist = (state.get("history") or [])[:-1]  # 末尾是本轮用户消息自身
    context = "\n".join(f"{h['role']}: {h['content']}" for h in hist[-6:])
    user = f"对话历史：\n{context}\n\n当前消息：{text}" if context else text
    # 1. 正则抽槽位，不依赖模型
    updates: dict = {
        "order_no": extract_order_no(text),
        "refund_amount": extract_refund_amount(text),
        "degraded": False,
    }

    # 2. LLM 分类，输出必须在封闭枚举内
    try:
        out = await ask_json(llm, system=SYSTEM, user=user, schema=IntentOutput)
        if out.intent in INTENTS:
            updates["intent"] = out.intent
            return updates
    except ValueError:
        pass

    # 3. 降级：关键词规则
    updates["intent"] = _keyword_intent(text)
    updates["degraded"] = True
    return updates
