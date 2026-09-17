from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.extract import order_no_in
from app.agent.scope import Scope
from app.agent.state import AgentState
from app.agent.tools.orders import get_order_detail



async def order_node(state: AgentState, *, session: AsyncSession, llm) -> dict:
    scope = Scope(role=state["actor_role"], user_id=state["actor_id"], merchant_id=state.get("merchant_id"))
    order_no = order_no_in(state)
    if not order_no:
        # 缺槽位：固定话术追问，不调 LLM
        return {"reply": "请提供一下订单号（如 #A1001），我帮您查询。", "widgets": []}

    detail = await get_order_detail(session, scope, order_no=order_no)
    if detail is None:
        return {"reply": f"没有找到订单 {order_no}，请确认订单号是否正确。", "widgets": []}

    widget = {"kind": "order", "data": detail}
    reply = await llm.complete(
        "你是电商客服，把订单信息组织成一句简短自然的回复，只输出这句话本身。",
        str(detail),
    )
    return {"reply": reply, "widgets": [widget]}
