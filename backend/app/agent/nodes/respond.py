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


GREETING = "您好，我是智能购物助手 🛍️\n\n可以帮您查询商品、订单物流，或办理退款。有什么可以帮您？"


async def ensure_conversation(session: AsyncSession, *, user_id: int,
                              conversation_id: int | None,
                              merchant_id: int | None = None) -> int:
    """API 层用：无会话则建，新会话由客服先打招呼（落库，历史可回看）。"""
    if conversation_id:
        return conversation_id
    conv = Conversation(user_id=user_id, merchant_id=merchant_id)
    session.add(conv)
    await session.flush()
    session.add(Message(conversation_id=conv.id, role="assistant", content=GREETING, widgets=[]))
    await session.flush()
    return conv.id
