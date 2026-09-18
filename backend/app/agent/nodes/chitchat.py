from app.agent.state import AgentState


_SYSTEM = "你是电商客服，用一句话简短友好地回应闲聊，不要推销。"


async def chitchat_node(state: AgentState, *, session, llm, emit=None) -> dict:
    reply = await llm.stream(_SYSTEM, state["text"], on_token=emit or (lambda t: None))
    return {"reply": reply, "widgets": []}
