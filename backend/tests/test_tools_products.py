from app.agent.scope import Scope
from app.agent.tools.products import get_product_detail, search_products


async def test_search_by_keyword(session, seeded):
    res = await search_products(session, Scope.for_user(seeded.user_id), keyword="耳机")
    assert len(res) >= 1
    assert all("耳机" in p["name"] for p in res)


async def test_search_returns_unit_price_as_str(session, seeded):
    res = await search_products(session, Scope.for_user(seeded.user_id), keyword="耳机")
    assert isinstance(res[0]["price"], str)  # Decimal 必须序列化，避免 JSON 精度丢失


async def test_search_empty_keyword_returns_top_n(session, seeded):
    res = await search_products(session, Scope.for_user(seeded.user_id), keyword=None, limit=5)
    assert len(res) == 5


async def test_product_detail_not_found_returns_none(session, seeded):
    assert await get_product_detail(session, Scope.for_user(seeded.user_id), product_id=99999) is None


async def test_browse_all_returns_hot_products_by_stock(session, seeded):
    """无关键词（浏览型）按库存降序取热门，limit 生效。"""
    from app.agent.tools.products import search_products

    all_hot = await search_products(session, Scope.for_user(seeded.user_id), keyword=None, limit=3)
    assert len(all_hot) == 3
    stocks = [p["stock"] for p in all_hot]
    assert stocks == sorted(stocks, reverse=True)
