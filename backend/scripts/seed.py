"""幂等演示数据：2 商家、1 演示用户、2 商家账号、22 商品、12 订单。

用法：uv run python -m scripts.seed
"""
import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.db import get_engine
from app.models import (
    Merchant, Order, OrderItem, OrderStatus, Product, User, UserRole,
)

MERCHANTS = [
    {"slug": "merchant-a", "name": "青柠数码"},
    {"slug": "merchant-b", "name": "山野户外"},
]

PRODUCTS = {
    "merchant-a": [
        ("降噪耳机 Pro", "数码", "599.00", 20, "主动降噪，40h 续航"),
        ("蓝牙耳机 Air", "数码", "199.00", 50, "半入耳，蓝牙 5.3"),
        ("机械键盘 K87", "数码", "399.00", 15, "87 键，热插拔轴"),
        ("4K 显示器 27\"", "数码", "1599.00", 8, "IPS，Type-C 90W"),
        ("无线充电板", "数码", "89.00", 100, "15W 快充"),
        ("USB-C 扩展坞", "数码", "249.00", 30, "8 合 1，千兆网口"),
        ("智能手表 Watch S", "数码", "899.00", 18, "血氧心率，14 天续航"),
        ("便携音箱 Boom", "数码", "299.00", 35, "IPX7 防水，24h 播放"),
        ("电动牙刷 Sonic", "数码", "179.00", 66, "声波震动，5 模式"),
        ("移动电源 2 万毫安", "数码", "129.00", 120, "22.5W 快充，双向 Type-C"),
        ("桌面显示器支架", "数码", "159.00", 45, "铝合金，气弹簧升降"),
    ],
    "merchant-b": [
        ("户外帐篷 3 人", "户外", "459.00", 12, "双层的晒，3kg"),
        ("睡袋 恒温 0°C", "户外", "329.00", 25, "羽绒填充"),
        ("登山杖 碳纤维", "户外", "269.00", 40, "三节伸缩"),
        ("头灯 1200 流明", "户外", "159.00", 60, "IPX8 防水"),
        ("露营折叠椅", "户外", "129.00", 80, "铝合金骨架"),
        ("保温水壶 1L", "户外", "99.00", 90, "24h 保温"),
        ("防潮垫 加厚", "户外", "79.00", 110, "铝膜反射，加厚 5cm"),
        ("户外冲锋衣", "户外", "699.00", 22, "三合一，防风防水"),
        ("快干毛巾 L", "户外", "39.00", 150, "超细纤维，速干抑菌"),
        ("野餐垫 2x2m", "户外", "69.00", 95, "加厚 PE，防潮耐磨"),
        ("驱蚊灯 充电款", "户外", "49.00", 88, "物理驱蚊，USB 充电"),
    ],
}

# (order_no, merchant_slug, status, total) —— 覆盖 5 幕演示与各转人工规则
ORDERS = [
    ("#A1001", "merchant-a", OrderStatus.PAID, "199.00"),      # 演示自动通过
    ("#A1002", "merchant-a", OrderStatus.SHIPPED, "599.00"),   # 金额+已发货双触发
    ("#A1003", "merchant-b", OrderStatus.DELIVERED, "89.00"),
    ("#A1004", "merchant-a", OrderStatus.PAID, "59.00"),
    ("#A1005", "merchant-a", OrderStatus.SHIPPED, "129.00"),
    ("#A1006", "merchant-b", OrderStatus.DELIVERED, "459.00"), # 已签收转人工
    ("#A1007", "merchant-b", OrderStatus.PAID, "329.00"),
    ("#A1008", "merchant-a", OrderStatus.CANCELLED, "249.00"), # 不可退
    ("#A1009", "merchant-b", OrderStatus.PAID, "699.00"),
    ("#A1010", "merchant-a", OrderStatus.DELIVERED, "179.00"), # 已签收转人工
    ("#A1011", "merchant-b", OrderStatus.SHIPPED, "39.00"),
    ("#A1012", "merchant-a", OrderStatus.PENDING, "299.00"),   # 待支付，不可退
]


async def seed(session) -> None:
    merchants: dict[str, Merchant] = {}
    for spec in MERCHANTS:
        m = (await session.execute(
            select(Merchant).where(Merchant.slug == spec["slug"]))).scalar_one_or_none()
        if m is None:
            m = Merchant(name=spec["name"], slug=spec["slug"])
            session.add(m)
            await session.flush()
        merchants[spec["slug"]] = m

    users: dict[str, User] = {}
    for name, role, slug in [
        ("演示用户", UserRole.USER, None),
        ("青柠数码客服", UserRole.MERCHANT, "merchant-a"),
        ("山野户外客服", UserRole.MERCHANT, "merchant-b"),
    ]:
        u = (await session.execute(select(User).where(User.name == name))).scalar_one_or_none()
        if u is None:
            u = User(name=name, role=role, merchant_id=merchants[slug].id if slug else None)
            session.add(u)
            await session.flush()
        users[name] = u

    demo = users["演示用户"]
    for slug, products in PRODUCTS.items():
        for name, category, price, stock, desc in products:
            p = (await session.execute(
                select(Product).where(Product.name == name))).scalar_one_or_none()
            if p is None:
                session.add(Product(merchant_id=merchants[slug].id, name=name,
                                    category=category, price=Decimal(price),
                                    stock=stock, description=desc))
    await session.flush()

    for order_no, slug, status, total in ORDERS:
        o = (await session.execute(
            select(Order).where(Order.order_no == order_no))).scalar_one_or_none()
        if o is None:
            o = Order(order_no=order_no, user_id=demo.id,
                      merchant_id=merchants[slug].id, status=status,
                      total_amount=Decimal(total))
            session.add(o)
            await session.flush()
            # 每单挂一条 order_item：按订单金额匹配该商家商品（无匹配则取第一个）
            p = (await session.execute(
                select(Product).where(Product.merchant_id == merchants[slug].id,
                                      Product.price == o.total_amount)
                .limit(1))).scalar_one_or_none() \
                or (await session.execute(
                    select(Product).where(Product.merchant_id == merchants[slug].id)
                    .limit(1))).scalar_one()
            session.add(OrderItem(order_id=o.id, product_id=p.id, quantity=1,
                                  unit_price=o.total_amount))


async def main() -> None:
    maker = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with maker() as session:
        await seed(session)
        await session.commit()
        n = (await session.execute(select(Order)))
        print("seed done:", len(n.all()), "orders")


if __name__ == "__main__":
    asyncio.run(main())
