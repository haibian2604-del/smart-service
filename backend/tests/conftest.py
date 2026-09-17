import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.models import Base, Merchant, Order, OrderItem, OrderStatus, Product, Refund, User, UserRole


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(get_settings().test_database_url, pool_pre_ping=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    conn = await engine.connect()
    trans = await conn.begin()
    sess = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield sess
    finally:
        await sess.close()
        await trans.rollback()
        await conn.close()


@pytest.fixture
async def client(session, engine):
    """ASGI 测试客户端：会话/LLM/checkpointer 全部替换为测试实现。"""
    from collections.abc import AsyncIterator
    from langgraph.checkpoint.memory import MemorySaver

    from app.core.db import get_session
    from app.main import app

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    app.state.checkpointer = MemorySaver()
    yield app
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def override_llm():
    """把进程级 LLM 换成 FakeLLM。
    裸用：安装 SmartFakeLLM（关键词意图分类 + 模板回复）；
    调用：override_llm(['resp1', ...]) 安装按序回放的 FakeLLM。"""
    from app.core.llm import set_llm
    from tests.fakes import SmartFakeLLM

    set_llm(SmartFakeLLM([]))  # 默认装智能桩

    def _install(responses):
        from tests.fakes import FakeLLM
        fake = FakeLLM(responses)
        set_llm(fake)
        return fake

    yield _install
    set_llm(None)


@pytest.fixture
async def seeded(session):
    """最小可控数据集：两租户、两商家账号、一个演示用户、少量订单/商品。"""
    from types import SimpleNamespace
    from decimal import Decimal

    ma = Merchant(name="商家 A", slug="merchant-a")
    mb = Merchant(name="商家 B", slug="merchant-b")
    session.add_all([ma, mb])
    await session.flush()

    ua = User(name="A 店客服", role=UserRole.MERCHANT, merchant_id=ma.id)
    ub = User(name="B 店客服", role=UserRole.MERCHANT, merchant_id=mb.id)
    demo = User(name="演示用户", role=UserRole.USER, merchant_id=None)
    session.add_all([ua, ub, demo])
    await session.flush()

    p = Product(merchant_id=ma.id, name="降噪耳机", category="数码",
                price=Decimal("599.00"), stock=10)
    session.add(p)
    await session.flush()
    for name, cat, price in [("蓝牙耳机 Air", "数码", "199.00"), ("机械键盘 K87", "数码", "399.00"),
                             ("露营折叠椅", "户外", "129.00"), ("保温水壶 1L", "户外", "99.00")]:
        session.add(Product(merchant_id=mb.id, name=name, category=cat,
                            price=Decimal(price), stock=20))
    await session.flush()

    def make_order(no, status, amount):
        o = Order(order_no=no, user_id=demo.id, merchant_id=ma.id,
                  status=status, total_amount=amount)
        session.add(o)
        return o

    o1 = make_order("#A1001", OrderStatus.PAID, Decimal("199.00"))
    o2 = make_order("#A1002", OrderStatus.SHIPPED, Decimal("599.00"))
    o3 = make_order("#A1003", OrderStatus.DELIVERED, Decimal("89.00"))
    o4 = make_order("#A1004", OrderStatus.CANCELLED, Decimal("59.00"))
    # 商家 B 的订单，验证隔离用
    ob = Order(order_no="#B1001", user_id=demo.id, merchant_id=mb.id,
               status=OrderStatus.PAID, total_amount=Decimal("29.00"))
    session.add_all([o1, o2, o3, o4, ob])
    await session.flush()

    session.add(OrderItem(order_id=o1.id, product_id=p.id, quantity=1,
                          unit_price=Decimal("199.00")))
    draft_refund = Refund(refund_no="#R2000", order_id=o1.id, user_id=demo.id,
                          merchant_id=ma.id, reason="测试草稿", amount=Decimal("199.00"))
    session.add(draft_refund)
    await session.flush()

    return SimpleNamespace(
        merchant_id=ma.id,
        other_merchant_id=mb.id,
        merchant_user_id=ua.id,
        other_merchant_user_id=ub.id,
        user_id=demo.id,
        user_order_count=5,
        order_id=o1.id,
        order_no=o1.order_no,
        paid_order_no=o1.order_no,
        shipped_order_no=o2.order_no,
        cancelled_order_no=o4.order_no,
        product_id=p.id,
        draft_refund_id=draft_refund.id,
    )
