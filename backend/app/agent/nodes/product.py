from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.extract import extract_keyword
from app.agent.scope import Scope
from app.agent.state import AgentState
from app.agent.tools.products import search_products


_REPLY_PROMPT = "把以下商品列表组织成一句简短自然的客服回复，只输出这句话本身：\n{data}"


async def product_node(state: AgentState, *, session: AsyncSession, llm, emit=None) -> dict:
    scope = Scope(role=state["actor_role"], user_id=state["actor_id"], merchant_id=state.get("merchant_id"))
    keyword = extract_keyword(state["text"]) or None
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
