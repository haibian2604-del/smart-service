from app.agent.prompts.persona import PERSONA
from app.agent.state import AgentState


_SYSTEM = PERSONA + "用户在和你闲聊，用一两句话简短友好地回应，不要推销。"


async def chitchat_node(state: AgentState, *, session, llm, emit=None) -> dict:
    reply = await llm.stream(_SYSTEM, state["text"], on_token=emit or (lambda t: None))
    return {"reply": reply, "widgets": []}
