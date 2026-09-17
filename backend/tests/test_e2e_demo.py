"""按 demo 五幕顺序跑完整链路，用真实 PG checkpointer（非 MemorySaver）。"""
import json

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import Refund, RefundStatus


def parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.replace("\r\n", "\n").strip().split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


async def chat(c: AsyncClient, user_id: int, message: str) -> list[dict]:
    r = await c.post("/api/chat/stream", json={"message": message},
                     headers={"X-Actor-Id": str(user_id)})
    assert r.status_code == 200
    return parse_sse(r.text)


async def test_act1_ask_for_product(client_pg, seeded, override_llm):
    """第一幕：问商品 → 意图路由 + 商品卡。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        events = await chat(c, seeded.user_id, "你们有蓝牙耳机吗")
    assert events[-1]["type"] == "done"
    widget = next(e for e in events if e["type"] == "widget")
    assert widget["kind"] == "product_list"
    assert any("耳机" in p["name"] for p in widget["data"])
    reply = "".join(e["text"] for e in events if e["type"] == "token")
    assert reply


async def test_act2_query_order_status(client_pg, seeded, override_llm):
    """第二幕：查订单 → 订单卡。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        events = await chat(c, seeded.user_id, f"我的订单 {seeded.order_no} 到哪了")
    widget = next(e for e in events if e["type"] == "widget")
    assert widget["kind"] == "order"
    assert widget["data"]["order_no"] == seeded.order_no


async def test_acts_3_to_5_refund_handoff_loop(client_pg, session, seeded, override_llm):
    """幕 3-5：申请退款 → 转人工 → 商家 A 可见 B 不可见 → 批准 → 用户轮询拿到结果。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # ── 幕 3：退款触发转人工 ──
        events = await chat(c, seeded.user_id, f"订单 {seeded.shipped_order_no} 我要退款")
        meta = next(e for e in events if e["type"] == "meta")
        handoff = next(e for e in events if e["type"] == "awaiting_human")
        task_id, conv_id = handoff["task_id"], meta["conversation_id"]

        # 幕 4：商家 A 看得到，商家 B 看不到（租户隔离演示）
        a = await c.get("/api/merchant/tasks?status=pending",
                        headers={"X-Actor-Id": str(seeded.merchant_user_id)})
        b = await c.get("/api/merchant/tasks?status=pending",
                        headers={"X-Actor-Id": str(seeded.other_merchant_user_id)})
        assert task_id in [t["id"] for t in a.json()]
        assert task_id not in [t["id"] for t in b.json()]

        # 幕 5 前置：轮询应显示挂起中
        status = (await c.get(f"/api/conversations/{conv_id}/status",
                              headers={"X-Actor-Id": str(seeded.user_id)})).json()
        assert status == {"pending_human": True, "task_id": task_id}

        # ── 幕 4：商家 A 批准，图恢复 ──
        resolve = await c.post(f"/api/merchant/tasks/{task_id}/resolve",
                               json={"decision": "approved", "note": "已核对"},
                               headers={"X-Actor-Id": str(seeded.merchant_user_id)})
        assert resolve.status_code == 200
        assert resolve.json()["refund_state"] == "refunded"

        # ── 幕 5：用户轮询拿到结果 ──
        status = (await c.get(f"/api/conversations/{conv_id}/status",
                              headers={"X-Actor-Id": str(seeded.user_id)})).json()
        assert status["pending_human"] is False

        conv = (await c.get(f"/api/conversations/{conv_id}",
                            headers={"X-Actor-Id": str(seeded.user_id)})).json()
        last = conv["messages"][-1]
        assert last["role"] == "assistant"
        assert "原路退回" in last["content"]

    # 落库终态
    rows = (await session.execute(
        select(Refund).where(Refund.status == RefundStatus.REFUNDED))).scalars().all()
    assert rows and all(r.amount is not None for r in rows)
