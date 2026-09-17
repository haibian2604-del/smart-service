from app.agent.state import AgentState
from app.core.llm import LLMClient

_SYSTEM = "你是电商客服，用一句话简短友好地回应闲聊，不要推销。"


async def chitchat_node(state: AgentState, *, session, llm: LLMClient) -> dict:
    reply = await llm.complete(_SYSTEM, state["text"])
    return {"reply": reply, "widgets": []}
