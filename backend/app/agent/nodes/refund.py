from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.extract import order_no_in
from app.agent.scope import Scope
from app.agent.state import AgentState
from app.agent.tools.refunds import check_refund_policy, create_refund_draft, submit_refund
from app.agent.tools.orders import get_order_detail
from app.core.config import get_settings
from app.core.llm import LLMClient


def _scope(state: AgentState) -> Scope:
    return Scope(role=state["actor_role"], user_id=state["actor_id"], merchant_id=state.get("merchant_id"))


async def refund_node(state: AgentState, *, session: AsyncSession, llm: LLMClient) -> dict:
    order_no = order_no_in(state)
    if not order_no:
        return {"reply": "请提供一下要退款的订单号（如 #A1001），我帮您办理。", "widgets": [],
                "refund_draft": None, "triggering_rule": None}

    # 金额没说就默认全额退
    amount = state.get("refund_amount")
    od = await get_order_detail(session, _scope(state), order_no=order_no)
    if od is None:
        return {"reply": f"没有找到订单 {order_no}，请确认订单号是否正确。", "widgets": []}
    if amount is None:
        from decimal import Decimal
        amount = Decimal(od["total_amount"])

    policy = await check_refund_policy(session, _scope(state), order_no=order_no,
                                       refund_amount=amount, user_text=state["text"])
    if not policy["eligible"]:
        reason_text = {
            "order_not_found": f"没有找到订单 {order_no}，请确认订单号是否正确。",
            "order_cancelled": "该订单已取消，无法申请退款。",
            "refund_already_exists": "该订单已有退款在处理中，请耐心等待。",
        }[policy["reason"]]
        return {"reply": reason_text, "widgets": [], "refund_draft": None, "triggering_rule": None}

    draft = await create_refund_draft(session, _scope(state), policy=policy)

    if policy["trigger"] is None:
        # 未触发任何护栏：自动通过，直接退
        await submit_refund(session, _scope(state), refund_id=draft["id"],
                            decision="approved", note="自动通过：未触发转人工规则")
        return {"refund_draft": draft, "triggering_rule": None, "refund_state": "refunded",
                "reply": f"您的退款 {draft['refund_no']}（¥{draft['amount']}）已自动受理，将原路退回。",
                "widgets": [{"kind": "refund", "data": {**draft, "trigger": None}}]}

    return {"refund_draft": draft, "triggering_rule": policy["trigger"], "refund_state": "draft",
            "widgets": [{"kind": "refund", "data": {**draft, "trigger": policy["trigger"]}}]}
