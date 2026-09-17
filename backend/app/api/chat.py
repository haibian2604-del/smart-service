import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import build_graph
from app.agent.nodes.respond import ensure_conversation
from app.agent.scope import Scope
from app.api.deps import Actor, get_current_actor
from app.core.db import get_session
from app.core.llm import get_llm
from app.models import Message

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str


def _sse(event_type: str, **payload) -> dict:
    return {"event": "message", "data": json.dumps({"type": event_type, **payload}, ensure_ascii=False)}


def _chunk(text: str, size: int = 8):
    for i in range(0, len(text), size):
        yield text[i:i + size]


@router.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, request: Request,
                      actor: Actor = Depends(get_current_actor),
                      session: AsyncSession = Depends(get_session)):
    from langgraph.errors import GraphInterrupt
    from langgraph.checkpoint.memory import MemorySaver

    async def gen():
        try:
            conversation_id = await ensure_conversation(session, user_id=actor.id,
                                                        conversation_id=body.conversation_id)
            session.add(Message(conversation_id=conversation_id, role="user", content=body.message))
            await session.flush()

            # 先发 meta：响应头+首包立即送达，LLM 期间前端可见“正在输入”
            yield _sse("meta", conversation_id=conversation_id)

            checkpointer = getattr(request.app.state, "checkpointer", None) or MemorySaver()
            graph = build_graph(session=session, llm=get_llm(), checkpointer=checkpointer)
            scope = actor.to_scope()
            config = {"configurable": {"thread_id": str(conversation_id)}}

            final = None
            try:
                final = await graph.ainvoke({
                    "text": body.message,
                    "actor_role": scope.role, "actor_id": scope.user_id,
                    "merchant_id": scope.merchant_id, "conversation_id": conversation_id,
                    "history": [{"role": "user", "content": body.message}],
                }, config=config)
            except GraphInterrupt:
                # interrupt 抛出：从 checkpoint 读回当前状态发事件
                snap = await graph.aget_state(config)
                final = snap.values

            if final:
                for w in final.get("widgets") or []:
                    yield _sse("widget", kind=w["kind"], data=w["data"])
                reply = final.get("reply") or ""
                for piece in _chunk(reply):
                    yield _sse("token", text=piece)
                if final.get("__interrupt__"):
                    task_id = final["__interrupt__"][0].value.get("task_id")
                    yield _sse("awaiting_human", task_id=task_id)
                yield _sse("done", conversation_id=conversation_id)
                await session.commit()
            else:
                await session.rollback()
                yield _sse("error", message="empty graph result")
        except Exception as e:  # demo：任何异常转 error 事件，不让连接挂死
            await session.rollback()
            yield _sse("error", message=str(e))

    return EventSourceResponse(gen(), headers={"X-Conversation-Id": str(body.conversation_id or 0)})


@router.get("/api/conversations/{conversation_id}/status")
async def get_conversation_status(conversation_id: int,
                                  actor: Actor = Depends(get_current_actor),
                                  session: AsyncSession = Depends(get_session)):
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.models import Conversation, HumanTask, TaskStatus

    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.user_id != actor.id:
        raise HTTPException(status_code=404)
    task = (await session.execute(
        select(HumanTask).where(HumanTask.thread_id == str(conversation_id),
                                HumanTask.status == TaskStatus.PENDING)
        .order_by(HumanTask.id.desc()).limit(1))).scalar_one_or_none()
    return {"pending_human": task is not None, "task_id": task.id if task else None}
@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: int,
                           actor: Actor = Depends(get_current_actor),
                           session: AsyncSession = Depends(get_session)):
    from app.models import Conversation
    from sqlalchemy import select

    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.user_id != actor.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    msgs = (await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id))).scalars().all()
    return {
        "id": conversation_id,
        "messages": [{"id": m.id, "role": m.role, "content": m.content,
                      "widgets": m.widgets or [], "tool_calls": m.tool_calls or []} for m in msgs],
    }
