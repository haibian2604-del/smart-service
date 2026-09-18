import json

from httpx import ASGITransport, AsyncClient

from app.main import app


def parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.replace("\r\n", "\n").strip().split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))
    return events


async def test_chat_stream_emits_done(client, seeded, override_llm):
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/chat/stream", json={"message": "有耳机吗"},
                            headers={"X-Actor-Id": str(seeded.user_id)})
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "widget" for e in events)


async def test_chat_stream_requires_actor(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/chat/stream", json={"message": "hi"})
    assert resp.status_code == 422  # 缺 header


async def test_chat_stream_emits_awaiting_human(client, seeded, override_llm):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/chat/stream",
                            json={"message": f"{seeded.shipped_order_no} 我要退款"},
                            headers={"X-Actor-Id": str(seeded.user_id)})
    events = parse_sse(resp.text)
    assert any(e["type"] == "awaiting_human" for e in events)


async def test_chat_stream_unknown_actor_401(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/chat/stream", json={"message": "hi"},
                            headers={"X-Actor-Id": "999999"})
    assert resp.status_code == 401


async def test_list_conversations_with_titles(client, seeded):
    """历史会话列表：只含本人会话，标题取首条用户消息。"""
    transport = ASGITransport(app=client)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/api/chat/stream", json={"message": "有耳机吗"},
                     headers={"X-Actor-Id": str(seeded.user_id)})
        r = await c.get("/api/conversations", headers={"X-Actor-Id": str(seeded.user_id)})
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list) and items
    assert all(i['title'] for i in items)
