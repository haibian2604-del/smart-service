from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.scope import Scope
from app.agent.tools.registry import register
from app.models import Product


def _to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "merchant_id": p.merchant_id,
        "name": p.name,
        "category": p.category,
        "price": str(p.price),
        "stock": p.stock,
        "description": p.description,
    }


@register("search_products")
async def search_products(session: AsyncSession, scope: Scope, *,
                          keyword: str | None, limit: int = 5) -> list[dict]:
    """商品是平台公开信息，两个角色都可查，不做 tenant 过滤。"""
    stmt = select(Product)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.category.ilike(like)))
    stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_dict(p) for p in rows]


@register("get_product_detail")
async def get_product_detail(session: AsyncSession, scope: Scope, *,
                             product_id: int) -> dict | None:
    p = await session.get(Product, product_id)
    return _to_dict(p) if p else None
