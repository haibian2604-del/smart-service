from httpx import ASGITransport, AsyncClient

from app.main import app


def sse_conv_id(raw: str) -> int:
    for block in raw.replace("\r\n", "\n").strip().split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:") and '"meta"' in line:
                import json
                return json.loads(line[5:])["conversation_id"]
    raise AssertionError("no meta event")


async def test_get_conversation_returns_messages(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/chat/stream", json={"message": "有耳机吗"},
                         headers={"X-Actor-Id": str(seeded.user_id)})
        conv_id = sse_conv_id(r.text)
        resp = await c.get(f"/api/conversations/{conv_id}",
                           headers={"X-Actor-Id": str(seeded.user_id)})
    body = resp.json()
    assert body["id"] == conv_id
    assert any(m["role"] == "user" for m in body["messages"])
    assert any(m["role"] == "assistant" for m in body["messages"])


async def test_status_pending_true_after_handoff(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/chat/stream",
                         json={"message": f"{seeded.shipped_order_no} 我要退款"},
                         headers={"X-Actor-Id": str(seeded.user_id)})
        conv_id = sse_conv_id(r.text)
        body = (await c.get(f"/api/conversations/{conv_id}/status",
                            headers={"X-Actor-Id": str(seeded.user_id)})).json()
    assert body["pending_human"] is True
    assert body["task_id"] is not None


async def test_customer_cannot_read_others_conversation(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/conversations/999999",
                           headers={"X-Actor-Id": str(seeded.user_id)})
    assert resp.status_code == 404
