from datetime import datetime, timezone

from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HumanTask, Order, Refund, RefundStatus, TaskStatus


async def human_review_node(state, *, session: AsyncSession, thread_id: str,
                            interrupt_fn=interrupt) -> dict:
    """挂起点：落库待办（幂等）→ 退款单转 pending → interrupt 等商家审批。"""
    draft = state.get("refund_draft") or {}
    refund_id = draft.get("id")
    merchant_id = draft.get("merchant_id")

    if merchant_id is None and refund_id is not None:
        _r = await session.get(Refund, refund_id)
        if _r:
            merchant_id = _r.merchant_id

    if refund_id is None:
        # 兜底：按订单号反查（checkpoint 重放时 state 可能不含 draft）
        from app.models import Order
        order = (await session.execute(
            select(Order).where(Order.order_no == state.get("order_no")))).scalar_one_or_none()
        if order is not None:
            merchant_id = order.merchant_id
            refund = (await session.execute(
                select(Refund).where(Refund.order_id == order.id)
                .order_by(Refund.id.desc()).limit(1))).scalar_one_or_none()
            if refund is not None:
                refund_id = refund.id
                draft = {"id": refund.id, "refund_no": refund.refund_no,
                         "amount": str(refund.amount), "merchant_id": order.merchant_id}

    task = (await session.execute(
        select(HumanTask).where(HumanTask.thread_id == thread_id)
    )).scalar_one_or_none()
    if task is None:
        task = HumanTask(
            merchant_id=merchant_id,
            thread_id=thread_id,
            type="refund_review",
            payload={
                "order_no": state.get("order_no"),
                "refund_id": refund_id,
                "refund_no": draft.get("refund_no"),
                "amount": draft.get("amount"),
                "reason": state["text"],
                "trigger": state.get("triggering_rule"),
            },
            status=TaskStatus.PENDING,
        )
        session.add(task)
        await session.flush()

    if refund_id is not None:
        r = await session.get(Refund, refund_id)
        r.status = RefundStatus.PENDING
        await session.flush()

    import inspect
    v = interrupt_fn({"task_id": task.id, "kind": "refund_review"})
    value = await v if inspect.isawaitable(v) else v
    # 单测桩直接返回包装 dict；真实 interrupt 在图内首跑时抛 GraphInterrupt，
    # resume 后才返回 Command(resume=...) 的值
    if isinstance(value, dict) and "__interrupt__" in value:
        return {"human_task_id": task.id, **value}
    return {"human_task_id": task.id, "human_decision": value.get("decision") if value else None,
            "human_note": value.get("note") if value else None}


async def finalize_refund_node(state, *, session: AsyncSession) -> dict:
    """按 human_decision 写库，并同步 HumanTask 终态。"""
    decision = state.get("human_decision")
    refund_id = state["refund_draft"]["id"]

    from app.agent.tools.refunds import submit_refund
    from app.agent.scope import Scope
    scope = Scope(role=state["actor_role"], user_id=state["actor_id"], merchant_id=state.get("merchant_id"))
    result = await submit_refund(session, scope, refund_id=refund_id,
                                 decision=decision, note=state.get("human_note"))

    task_id = state.get("human_task_id")
    if task_id:
        task = await session.get(HumanTask, task_id)
        if task:
            task.status = TaskStatus.APPROVED if decision == "approved" else TaskStatus.REJECTED
            task.assignee_id = scope.user_id
            task.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.flush()

    refund_state = "refunded" if decision == "approved" else "rejected"
    amount = state["refund_draft"].get("amount", "")
    reply = (f"您的退款申请已通过，¥{amount} 将原路退回。" if decision == "approved"
             else f"很抱歉，您的退款申请未通过：{state.get('human_note') or '商家未说明原因'}。")
    return {"refund_state": refund_state, "reply": reply}
