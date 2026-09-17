import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Merchant, User, UserRole


async def test_create_merchant_and_merchant_user(session):
    m = Merchant(name="商家 A", slug="merchant-a")
    session.add(m)
    await session.flush()
    u = User(name="A 店客服", role=UserRole.MERCHANT, merchant_id=m.id)
    session.add(u)
    await session.flush()
    assert u.merchant_id == m.id
    assert u.role is UserRole.MERCHANT


async def test_merchant_slug_is_unique(session):
    session.add_all([Merchant(name="A", slug="dup"), Merchant(name="B", slug="dup")])
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_merchant_role_requires_merchant_id(session):
    session.add(User(name="无租户商家", role=UserRole.MERCHANT, merchant_id=None))
    with pytest.raises(IntegrityError):
        await session.flush()
