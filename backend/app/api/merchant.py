from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph
from app.api.deps import Actor, get_current_actor
from app.core.db import get_session
from app.core.llm import get_llm
from app.models import HumanTask, TaskStatus

router = APIRouter()


class ResolveRequest(BaseModel):
    decision: str
    note: str | None = None


@router.get("/api/merchant/tasks")
async def list_pending_tasks(status: str = "pending",
                             actor: Actor = Depends(get_current_actor),
                             session: AsyncSession = Depends(get_session)):
    if actor.role != "merchant":
        raise HTTPException(status_code=403, detail="merchant_only")
    stmt = select(HumanTask).where(HumanTask.merchant_id == actor.merchant_id,
                                   HumanTask.status == TaskStatus.PENDING).order_by(HumanTask.id)
    rows = (await session.execute(stmt)).scalars().all()
    return [{"id": t.id, "type": t.type, "status": t.status.value, "payload": t.payload,
             "thread_id": t.thread_id, "created_at": t.created_at.isoformat()} for t in rows]


@router.post("/api/merchant/tasks/{task_id}/resolve")
async def resolve_task(task_id: int, body: ResolveRequest, request: Request,
                       actor: Actor = Depends(get_current_actor),
                       session: AsyncSession = Depends(get_session)):
    from langgraph.types import Command

    if actor.role != "merchant":
        raise HTTPException(status_code=403, detail="merchant_only")
    # id + merchant_id 双条件，防存在性泄露
    task = (await session.execute(
        select(HumanTask).where(HumanTask.id == task_id,
                                HumanTask.merchant_id == actor.merchant_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=409, detail="task_already_resolved")

    task.status = TaskStatus.APPROVED if body.decision == "approved" else TaskStatus.REJECTED
    task.assignee_id = actor.id
    task.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.flush()

    checkpointer = getattr(request.app.state, "checkpointer")
    graph = build_graph(session=session, llm=get_llm(), checkpointer=checkpointer)
    result = await graph.ainvoke(
        Command(resume={"decision": body.decision, "note": body.note}),
        config={"configurable": {"thread_id": task.thread_id}},
    )
    return {"refund_state": result.get("refund_state"), "reply": result.get("reply")}
