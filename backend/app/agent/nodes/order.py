from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.extract import order_no_in
from app.agent.scope import Scope
from app.agent.state import AgentState
from app.agent.tools.orders import get_order_detail, list_my_orders



async def order_node(state: AgentState, *, session: AsyncSession, llm) -> dict:
    scope = Scope(role=state["actor_role"], user_id=state["actor_id"], merchant_id=state.get("merchant_id"))
    order_no = order_no_in(state)
    if not order_no:
        # 缺订单号：查名下全部订单，总结购买过的商品
        orders = await list_my_orders(session, scope)
        if not orders:
            return {"reply": "您还没有任何订单，去商城逛逛吧！", "widgets": []}
        reply = await llm.complete(
            "你是电商客服，用户询问自己买过哪些东西。根据订单列表（含商品明细）用两三句话自然总结，只输出这段话本身。",
            str(orders),
        )
        return {"reply": reply, "widgets": [{"kind": "order", "data": o} for o in orders]}

    detail = await get_order_detail(session, scope, order_no=order_no)
    if detail is None:
        return {"reply": f"没有找到订单 {order_no}，请确认订单号是否正确。", "widgets": []}

    widget = {"kind": "order", "data": detail}
    reply = await llm.complete(
        "你是电商客服，把订单信息组织成一句简短自然的回复，只输出这句话本身。",
        str(detail),
    )
    return {"reply": reply, "widgets": [widget]}
