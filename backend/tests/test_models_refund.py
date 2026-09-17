from decimal import Decimal

from app.models import Conversation, HumanTask, Message, Refund, RefundStatus, TaskStatus


async def test_refund_status_defaults_to_draft(session, seeded):
    r = Refund(refund_no="#R2001", order_id=seeded.order_id, user_id=seeded.user_id,
               merchant_id=seeded.merchant_id, reason="不想要了",
               amount=Decimal("199.00"))
    session.add(r)
    await session.flush()
    assert r.status is RefundStatus.DRAFT


async def test_human_task_links_thread(session, seeded):
    t = HumanTask(merchant_id=seeded.merchant_id, thread_id="conv-1",
                  type="refund_review", payload={"order_no": "#A1001"})
    session.add(t)
    await session.flush()
    assert t.status is TaskStatus.PENDING
    assert t.payload["order_no"] == "#A1001"


async def test_message_stores_widgets(session, seeded):
    conv = Conversation(user_id=seeded.user_id)
    session.add(conv)
    await session.flush()
    m = Message(conversation_id=conv.id, role="assistant", content="订单已发货",
                widgets=[{"kind": "order", "data": {"order_no": "#A1001"}}])
    session.add(m)
    await session.flush()
    assert m.widgets[0]["kind"] == "order"
