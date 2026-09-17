from sqlalchemy import func, select

from app.models import Merchant, Order, OrderStatus, Product, User
from scripts.seed import seed


async def test_seed_is_idempotent(session):
    await seed(session)
    first = (await session.execute(select(func.count(Merchant.id)))).scalar_one()
    await seed(session)
    second = (await session.execute(select(func.count(Merchant.id)))).scalar_one()
    assert first == second == 2


async def test_seed_covers_all_order_statuses(session):
    await seed(session)
    rows = (await session.execute(select(Order.status).distinct())).scalars().all()
    assert {OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.PAID} <= set(rows)


async def test_seed_creates_demo_user_and_merchant_accounts(session):
    await seed(session)
    users = (await session.execute(select(User))).scalars().all()
    assert sum(u.role.value == "user" for u in users) == 1
    assert sum(u.role.value == "merchant" for u in users) == 2


async def test_seed_products_belong_to_merchants(session):
    await seed(session)
    products = (await session.execute(select(Product))).scalars().all()
    assert len(products) >= 12
    merchant_ids = set((await session.execute(select(Merchant.id))).scalars().all())
    assert all(p.merchant_id in merchant_ids for p in products)
