from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.policy import detect_human_trigger
from app.agent.scope import Scope
from app.agent.tools.orders import _normalize_order_no, _scope_filter
from app.models import Order, Refund, RefundStatus

# 这些状态表示已有退款在途，不可重复申请
_BLOCKING_REFUND_STATUSES = (RefundStatus.PENDING, RefundStatus.APPROVED, RefundStatus.REFUNDED)


async def _next_refund_no(session: AsyncSession) -> str:
    max_id = (await session.execute(select(func.max(Refund.id)))).scalar() or 0
    return f"#R{2000 + max_id + 1}"


async def check_refund_policy(session: AsyncSession, scope: Scope, *,
                              order_no: str, refund_amount: Decimal, user_text: str) -> dict:
    o = (await session.execute(
        select(Order).where(_scope_filter(scope), Order.order_no == _normalize_order_no(order_no))
    )).scalar_one_or_none()
    if o is None:
        return {"eligible": False, "reason": "order_not_found", "order": None, "trigger": None}

    active = (await session.execute(
        select(func.count(Refund.id)).where(
            Refund.order_id == o.id, Refund.status.in_(_BLOCKING_REFUND_STATUSES))
    )).scalar_one()
    if o.status == "cancelled":
        return {"eligible": False, "reason": "order_cancelled", "order": o.order_no, "trigger": None}
    if active:
        return {"eligible": False, "reason": "refund_already_exists", "order": o.order_no, "trigger": None}

    trigger = detect_human_trigger(order_status=o.status, refund_amount=refund_amount,
                                   user_text=user_text)
    return {
        "eligible": True,
        "reason": None,
        "order": o.order_no,
        "trigger": trigger.value if trigger else None,
        "order_id": o.id,
        "merchant_id": o.merchant_id,
        "user_id": o.user_id,
        "amount": str(refund_amount),
    }


async def create_refund_draft(session: AsyncSession, scope: Scope, *, policy: dict) -> dict:
    r = Refund(
        refund_no=await _next_refund_no(session),
        order_id=policy["order_id"],
        user_id=policy["user_id"],
        merchant_id=policy["merchant_id"],
        reason=policy.get("reason"),
        amount=Decimal(policy["amount"]),
        status=RefundStatus.DRAFT,
    )
    session.add(r)
    await session.flush()
    return {"id": r.id, "refund_no": r.refund_no, "amount": str(r.amount), "status": r.status.value}


async def submit_refund(session: AsyncSession, scope: Scope, *,
                        refund_id: int, decision: str, note: str | None) -> dict:
    r = await session.get(Refund, refund_id)
    r.status = RefundStatus.REFUNDED if decision == "approved" else RefundStatus.REJECTED
    r.review_note = note
    r.reviewed_by = scope.user_id
    r.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.flush()
    return {"id": r.id, "refund_no": r.refund_no, "status": r.status.value}
