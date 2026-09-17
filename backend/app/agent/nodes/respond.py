from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.models import Conversation, Message


async def respond_node(state: AgentState, *, session: AsyncSession) -> dict:
    """本轮出口：归一化 refund_state；有会话上下文时落库消息。"""
    updates: dict = {"refund_state": state.get("refund_state"),
                     "history": [{"role": "assistant", "content": state.get("reply") or ""}]}

    conversation_id = state.get("conversation_id")
    if conversation_id:
        session.add(Message(conversation_id=conversation_id, role="assistant",
                            content=state.get("reply") or "",
                            widgets=state.get("widgets") or []))
        await session.flush()
    return updates


async def ensure_conversation(session: AsyncSession, *, user_id: int,
                              conversation_id: int | None) -> int:
    """API 层用：无会话则建。"""
    if conversation_id:
        return conversation_id
    conv = Conversation(user_id=user_id)
    session.add(conv)
    await session.flush()
    return conv.id
