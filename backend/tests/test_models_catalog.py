from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Order, OrderItem, OrderStatus, Product


async def test_product_belongs_to_merchant(session, seeded):
    p = Product(merchant_id=seeded.merchant_id, name="降噪耳机",
                category="数码", price=Decimal("599.00"), stock=10)
    session.add(p)
    await session.flush()
    assert p.merchant_id == seeded.merchant_id


async def test_order_no_is_unique(session, seeded):
    dup = Order(order_no=seeded.order_no, user_id=seeded.user_id,
                merchant_id=seeded.merchant_id, status=OrderStatus.PAID,
                total_amount=Decimal("199.00"))
    session.add(dup)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_order_status_is_constrained(session, seeded):
    bad = Order(order_no="#A9998", user_id=seeded.user_id,
                merchant_id=seeded.merchant_id, status="not_a_status",
                total_amount=Decimal("1.00"))
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_order_item_links_product(session, seeded):
    item = OrderItem(order_id=seeded.order_id, product_id=seeded.product_id,
                     quantity=2, unit_price=Decimal("89.00"))
    session.add(item)
    await session.flush()
    assert item.quantity == 2
