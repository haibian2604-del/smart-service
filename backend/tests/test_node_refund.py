from decimal import Decimal

from sqlalchemy import select

from app.agent.nodes.human import finalize_refund_node, human_review_node
from app.agent.nodes.refund import refund_node
from app.agent.scope import Scope
from app.agent.state import new_state
from app.models import HumanTask, Refund, RefundStatus
from tests.fakes import FakeLLM


async def test_refund_node_missing_order_no_asks_back(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="我要退款")
    state["intent"] = "refund"
    out = await refund_node(state, session=session, llm=FakeLLM([]))
    assert "订单号" in out["reply"]


async def test_refund_node_auto_path_sets_no_trigger(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="不想要了")
    state.update(intent="refund", order_no=seeded.paid_order_no, refund_amount=Decimal("50.00"))
    out = await refund_node(state, session=session, llm=FakeLLM([]))
    assert out["triggering_rule"] is None
    assert out["refund_state"] == "refunded"  # 自动通过直接退


async def test_refund_node_human_path_sets_trigger(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", order_no=seeded.shipped_order_no, refund_amount=Decimal("599.00"))
    out = await refund_node(state, session=session, llm=FakeLLM([]))
    assert out["triggering_rule"] == "already_shipped"
    assert out["refund_draft"]["status"] == "draft"


async def test_human_review_node_creates_task_and_interrupts(session, seeded):
    from types import SimpleNamespace

    async def fake_interrupt(value):
        return {"__interrupt__": [SimpleNamespace(value=value)]}

    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", order_no=seeded.shipped_order_no,
                 refund_amount=Decimal("599.00"), refund_draft={"id": seeded.draft_refund_id, "amount": "599.00"},
                 triggering_rule="already_shipped")
    out = await human_review_node(state, session=session, thread_id="conv-1",
                                  interrupt_fn=fake_interrupt)
    task = (await session.execute(select(HumanTask).where(HumanTask.thread_id == "conv-1"))).scalar_one()
    assert task.merchant_id == seeded.merchant_id
    assert task.status.value == "pending"
    assert out["__interrupt__"][0].value["task_id"] == task.id
    # 退款单应已转 pending
    r = (await session.execute(select(Refund).where(Refund.id == seeded.draft_refund_id))).scalar_one()
    assert r.status is RefundStatus.PENDING


async def test_human_review_node_is_idempotent_per_thread(session, seeded):
    """重复进入不能建出两条待办（防 checkpoint 重放）。"""
    from types import SimpleNamespace

    async def fake_interrupt(value):
        return {"__interrupt__": [SimpleNamespace(value=value)]}

    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", order_no=seeded.shipped_order_no,
                 refund_amount=Decimal("599.00"), triggering_rule="already_shipped")
    await human_review_node(state, session=session, thread_id="conv-1",
                            interrupt_fn=fake_interrupt)
    await human_review_node(state, session=session, thread_id="conv-1",
                            interrupt_fn=fake_interrupt)
    tasks = (await session.execute(select(HumanTask).where(HumanTask.thread_id == "conv-1"))).scalars().all()
    assert len(tasks) == 1


async def test_finalize_refund_approved_marks_refunded(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", refund_draft={"id": seeded.draft_refund_id},
                 human_decision="approved")
    out = await finalize_refund_node(state, session=session)
    row = (await session.execute(select(Refund).where(Refund.id == seeded.draft_refund_id))).scalar_one()
    assert row.status is RefundStatus.REFUNDED
    assert out["refund_state"] == "refunded"


async def test_finalize_refund_rejected_records_note(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", refund_draft={"id": seeded.draft_refund_id},
                 human_decision="rejected", human_note="超期")
    await finalize_refund_node(state, session=session)
    row = (await session.execute(select(Refund).where(Refund.id == seeded.draft_refund_id))).scalar_one()
    assert row.status is RefundStatus.REJECTED and row.review_note == "超期"
