from decimal import Decimal

from sqlalchemy import select

from app.agent.scope import Scope
from app.agent.tools.refunds import check_refund_policy, create_refund_draft, submit_refund
from app.models import Refund, RefundStatus


async def test_policy_marks_shipped_order_needs_human(session, seeded):
    r = await check_refund_policy(
        session, Scope.for_user(seeded.user_id),
        order_no=seeded.shipped_order_no, refund_amount=Decimal("599.00"),
        user_text="我要退款",
    )
    assert r["eligible"] is True
    assert r["trigger"] == "already_shipped"


async def test_policy_marks_small_paid_order_auto(session, seeded):
    r = await check_refund_policy(
        session, Scope.for_user(seeded.user_id),
        order_no=seeded.paid_order_no, refund_amount=Decimal("50.00"),
        user_text="不想要了",
    )
    assert r["trigger"] is None


async def test_policy_rejects_non_refundable_status(session, seeded):
    r = await check_refund_policy(
        session, Scope.for_user(seeded.user_id),
        order_no=seeded.cancelled_order_no, refund_amount=Decimal("10.00"),
        user_text="退款",
    )
    assert r["eligible"] is False


async def test_policy_rejects_order_with_active_refund(session, seeded):
    """已有 pending/approved/refunded 退款的订单不可重复退（draft 不拦）。"""
    from app.models import Order, OrderStatus
    o = Order(order_no="#A7777", user_id=seeded.user_id, merchant_id=seeded.merchant_id,
              status=OrderStatus.PAID, total_amount=Decimal("30.00"))
    session.add(o)
    await session.flush()
    session.add(Refund(refund_no="#R7001", order_id=o.id, user_id=seeded.user_id,
                       merchant_id=seeded.merchant_id, amount=Decimal("30.00"),
                       status=RefundStatus.PENDING))
    await session.flush()
    r = await check_refund_policy(session, Scope.for_user(seeded.user_id),
                                  order_no="#A7777", refund_amount=Decimal("30.00"),
                                  user_text="退款")
    assert r["eligible"] is False and r["reason"] == "refund_already_exists"


async def test_policy_respects_scope(session, seeded):
    scope_b = Scope.for_merchant(seeded.other_merchant_user_id, seeded.other_merchant_id)
    r = await check_refund_policy(session, scope_b, order_no=seeded.order_no,
                                  refund_amount=Decimal("10.00"), user_text="退款")
    assert r["eligible"] is False and r["reason"] == "order_not_found"


async def test_create_draft_then_submit_advances_status(session, seeded):
    policy = await check_refund_policy(session, Scope.for_user(seeded.user_id),
                                       order_no=seeded.paid_order_no,
                                       refund_amount=Decimal("50.00"), user_text="不想要了")
    draft = await create_refund_draft(session, Scope.for_user(seeded.user_id), policy=policy)
    assert draft["status"] == RefundStatus.DRAFT.value

    await submit_refund(session, Scope.for_user(seeded.user_id),
                        refund_id=draft["id"], decision="approved", note=None)
    row = (await session.execute(select(Refund).where(Refund.id == draft["id"]))).scalar_one()
    assert row.status is RefundStatus.REFUNDED


async def test_submit_rejected_records_note(session, seeded):
    policy = await check_refund_policy(session, Scope.for_user(seeded.user_id),
                                       order_no=seeded.paid_order_no,
                                       refund_amount=Decimal("50.00"), user_text="不想要了")
    draft = await create_refund_draft(session, Scope.for_user(seeded.user_id), policy=policy)
    await submit_refund(session, Scope.for_user(seeded.user_id),
                        refund_id=draft["id"], decision="rejected", note="超出退款期限")
    row = (await session.execute(select(Refund).where(Refund.id == draft["id"]))).scalar_one()
    assert row.status is RefundStatus.REJECTED and row.review_note == "超出退款期限"


