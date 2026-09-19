import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.extract import extract_keyword
from app.agent.prompts.persona import PERSONA
from app.agent.scope import Scope
from app.agent.state import AgentState
from app.agent.tools.products import search_products


_REPLY_PROMPT = PERSONA + """用户在询问是否有某类商品在售。请按以下结构用自然中文回复：
1. 先直接回答有没有（例如「有的」/「暂时没有」）；
2. 有几款就逐款简要介绍热门商品（名称 + 价格 + 一句卖点），不要大段罗列参数；
3. 结尾邀请用户了解更多或直接下单。
只输出回复本身，不要标题和序号。商品数据：
{data}"""


async def product_node(state: AgentState, *, session: AsyncSession, llm, emit=None) -> dict:
    scope = Scope(role=state["actor_role"], user_id=state["actor_id"], merchant_id=state.get("merchant_id"))
    text = state["text"]
    # 「有哪些/什么商品」类浏览型问题：不按关键词过滤，直接列全部在售
    keyword = None if re.search(r"有哪些|有什么|哪些商品|什么商品|所有|全部|在售|都卖|都有些", text) \
        else extract_keyword(text) or None
    products = await search_products(session, scope, keyword=keyword)
    if not products:
        return {"reply": "暂时没有找到相关商品，您可以换个说法试试。", "widgets": []}
    widget = {"kind": "product_list", "data": products}
    reply = await llm.stream(
        "你是电商客服，回复要简短自然。",
        _REPLY_PROMPT.format(data=str(products)),
        on_token=emit or (lambda t: None),
    )
    return {"reply": reply, "widgets": [widget]}
