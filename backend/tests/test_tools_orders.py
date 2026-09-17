from sqlalchemy import select
from app.models import User, UserRole
from app.agent.scope import Scope
from app.agent.tools.orders import get_order_detail, list_my_orders


async def test_user_sees_only_own_orders(session, seeded):
    res = await list_my_orders(session, Scope.for_user(seeded.user_id))
    order_nos = {o["order_no"] for o in res}
    assert seeded.order_no in order_nos
    assert len(res) == seeded.user_order_count


async def test_user_cannot_read_others_order(session, seeded):
    other = User(name="别人", role=UserRole.USER)
    session.add(other)
    await session.flush()
    assert await get_order_detail(session, Scope.for_user(other.id), order_no=seeded.order_no) is None


async def test_merchant_sees_only_own_tenant_orders(session, seeded):
    scope = Scope.for_merchant(seeded.merchant_user_id, seeded.merchant_id)
    res = await list_my_orders(session, scope)
    assert res and all(o["merchant_id"] == seeded.merchant_id for o in res)


async def test_merchant_cannot_read_other_tenant_order(session, seeded):
    """关键越权测试：商家 B 查商家 A 的订单必须拿不到。"""
    scope_b = Scope.for_merchant(seeded.other_merchant_user_id, seeded.other_merchant_id)
    assert await get_order_detail(session, scope_b, order_no=seeded.order_no) is None


async def test_order_detail_includes_items(session, seeded):
    detail = await get_order_detail(session, Scope.for_user(seeded.user_id), order_no=seeded.order_no)
    assert detail["items"] and detail["items"][0]["quantity"] >= 1
