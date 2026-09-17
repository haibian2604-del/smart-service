from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import Refund, RefundStatus


def sse_meta(raw: str) -> dict:
    import json
    out = {}
    for block in raw.replace("\r\n", "\n").strip().split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                e = json.loads(line[5:])
                if e["type"] in ("meta", "awaiting_human"):
                    out.update(e)
    return out


async def make_interrupted_task(c, seeded, override_llm):
    r = await c.post("/api/chat/stream",
                     json={"message": f"{seeded.shipped_order_no} 我要退款"},
                     headers={"X-Actor-Id": str(seeded.user_id)})
    events = sse_meta(r.text)
    return events["task_id"], events["conversation_id"]


async def test_list_pending_tasks_scoped_to_tenant(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        task_id, _ = await make_interrupted_task(c, seeded, override_llm)
        a = await c.get("/api/merchant/tasks?status=pending",
                        headers={"X-Actor-Id": str(seeded.merchant_user_id)})
        b = await c.get("/api/merchant/tasks?status=pending",
                        headers={"X-Actor-Id": str(seeded.other_merchant_user_id)})
    assert [t["id"] for t in a.json()] == [task_id]
    assert b.json() == []  # 商家 B 看不到


async def test_customer_cannot_access_merchant_api(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/merchant/tasks", headers={"X-Actor-Id": str(seeded.user_id)})
    assert resp.status_code == 403


async def test_resolve_approves_and_resumes_graph(client, session, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        task_id, _ = await make_interrupted_task(c, seeded, override_llm)
        resp = await c.post(f"/api/merchant/tasks/{task_id}/resolve",
                            json={"decision": "approved", "note": "已核对"},
                            headers={"X-Actor-Id": str(seeded.merchant_user_id)})
    assert resp.status_code == 200
    assert resp.json()["refund_state"] == "refunded"


async def test_resolve_cross_tenant_returns_404(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        task_id, _ = await make_interrupted_task(c, seeded, override_llm)
        resp = await c.post(f"/api/merchant/tasks/{task_id}/resolve",
                            json={"decision": "approved"},
                            headers={"X-Actor-Id": str(seeded.other_merchant_user_id)})
    assert resp.status_code == 404


async def test_resolve_twice_returns_409(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        task_id, _ = await make_interrupted_task(c, seeded, override_llm)
        h = {"X-Actor-Id": str(seeded.merchant_user_id)}
        body = {"decision": "approved"}
        await c.post(f"/api/merchant/tasks/{task_id}/resolve", json=body, headers=h)
        again = await c.post(f"/api/merchant/tasks/{task_id}/resolve", json=body, headers=h)
    assert again.status_code == 409
