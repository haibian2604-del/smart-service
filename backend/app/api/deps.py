from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.scope import Scope
from app.core.db import get_session
from app.models import User


@dataclass(frozen=True, slots=True)
class Actor:
    id: int
    role: Literal["user", "merchant"]
    merchant_id: int | None
    name: str

    def to_scope(self) -> Scope:
        if self.role == "merchant":
            return Scope.for_merchant(user_id=self.id, merchant_id=self.merchant_id)
        return Scope.for_user(user_id=self.id)


async def resolve_actor(session: AsyncSession, *, x_actor_id: int) -> Actor:
    u = await session.get(User, x_actor_id)
    if u is None:
        raise HTTPException(status_code=401, detail="actor_not_found")
    return Actor(id=u.id, role=u.role.value, merchant_id=u.merchant_id, name=u.name)


async def get_current_actor(
    session: AsyncSession = Depends(get_session),
    x_actor_id: int = Header(..., alias="X-Actor-Id"),
) -> Actor:
    return await resolve_actor(session, x_actor_id=x_actor_id)
