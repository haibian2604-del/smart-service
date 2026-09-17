from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import chitchat, classify, human, order, product, refund, respond
from app.agent.state import AgentState



def route_after_classify(state: AgentState) -> str:
    return state["intent"] if state["intent"] in ("product", "order", "refund", "chitchat") else "unknown"


def route_after_refund(state: AgentState) -> str:
    """追问路径（无 draft）或自动通过（无触发）都不进人工。"""
    if state.get("refund_draft") is None or state.get("triggering_rule") is None:
        return "respond"
    return "human_review"


def build_graph(*, session: AsyncSession, llm,
                checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    g = StateGraph(AgentState)

    g.add_node("classify", partial(classify.classify_node, llm=llm))
    g.add_node("product_node", partial(product.product_node, session=session, llm=llm))
    g.add_node("order_node", partial(order.order_node, session=session, llm=llm))
    g.add_node("refund_node", partial(refund.refund_node, session=session, llm=llm))
    g.add_node("chitchat_node", partial(chitchat.chitchat_node, session=session, llm=llm))
    g.add_node("unknown_node", partial(_unknown_node, llm=llm))
    g.add_node("human_review", partial(_human_review, session=session))
    g.add_node("finalize_refund", partial(human.finalize_refund_node, session=session))
    g.add_node("respond", partial(respond.respond_node, session=session))

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route_after_classify, {
        "product": "product_node", "order": "order_node", "refund": "refund_node",
        "chitchat": "chitchat_node", "unknown": "unknown_node",
    })
    for n in ("product_node", "order_node", "chitchat_node", "unknown_node"):
        g.add_edge(n, "respond")
    g.add_conditional_edges("refund_node", route_after_refund,
                            {"respond": "respond", "human_review": "human_review"})
    g.add_edge("human_review", "finalize_refund")
    g.add_edge("finalize_refund", "respond")
    g.add_edge("respond", END)

    return g.compile(checkpointer=checkpointer)


from langchain_core.runnables import RunnableConfig


async def _human_review(state: AgentState, config: RunnableConfig, *, session: AsyncSession) -> dict:
    thread_id = config["configurable"]["thread_id"]
    return await human.human_review_node(state, session=session, thread_id=thread_id)


async def _unknown_node(state: AgentState, *, llm) -> dict:
    reply = await llm.complete("你是电商客服，简短回复。", "用户说了无法理解的话，请礼貌引导：\n" + state["text"])
    return {"reply": reply, "widgets": []}
