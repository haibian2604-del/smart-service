from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.scope import Scope
from app.agent.tools.registry import register
from app.models import Order, OrderItem


def _scope_filter(scope: Scope):
    """租户隔离核心：过滤条件进 where，而不是先查后校验。"""
    if scope.role == "user":
        return Order.user_id == scope.user_id
    return Order.merchant_id == scope.merchant_id


def _order_dict(o: Order, *, with_items: bool = False) -> dict:
    d = {
        "id": o.id,
        "order_no": o.order_no,
        "merchant_id": o.merchant_id,
        "status": o.status.value,
        "total_amount": str(o.total_amount),
        "created_at": o.created_at.isoformat(),
        "shipped_at": o.shipped_at.isoformat() if o.shipped_at else None,
        "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
    }
    if with_items:
        d["items"] = [
            {"name": it.product.name, "quantity": it.quantity, "unit_price": str(it.unit_price)}
            for it in o.items
        ]
    return d


def _normalize_order_no(order_no: str) -> str:
    order_no = order_no.strip().lstrip("#").upper()
    return f"#{order_no}"


async def _get_scoped_order(session: AsyncSession, scope: Scope, *, order_no: str) -> Order | None:
    stmt = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .where(_scope_filter(scope), Order.order_no == _normalize_order_no(order_no))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


@register("list_my_orders")
async def list_my_orders(session: AsyncSession, scope: Scope) -> list[dict]:
    stmt = (
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .where(_scope_filter(scope))
        .order_by(Order.id.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_order_dict(o, with_items=True) for o in rows]


@register("get_order_detail")
async def get_order_detail(session: AsyncSession, scope: Scope, *, order_no: str) -> dict | None:
    o = await _get_scoped_order(session, scope, order_no=order_no)
    return _order_dict(o, with_items=True) if o else None
