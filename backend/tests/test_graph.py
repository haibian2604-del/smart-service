from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agent.graph import build_graph
from tests.fakes import FakeLLM


def make_graph(session, llm):
    return build_graph(session=session, llm=llm, checkpointer=MemorySaver())


async def test_graph_routes_product_intent(session, seeded):
    graph = make_graph(session, FakeLLM(['{"intent":"product"}', "为您找到以下商品"]))
    out = await graph.ainvoke(
        {"text": "有耳机吗", "actor_role": "user", "actor_id": seeded.user_id, "merchant_id": None},
        config={"configurable": {"thread_id": "t-product"}},
    )
    assert out["intent"] == "product"
    assert out["reply"]


async def test_graph_unknown_intent_does_not_crash(session, seeded):
    graph = make_graph(session, FakeLLM(["垃圾", "垃圾", "抱歉，没能理解您的意思。"]))
    out = await graph.ainvoke(
        {"text": "???", "actor_role": "user", "actor_id": seeded.user_id, "merchant_id": None},
        config={"configurable": {"thread_id": "t-unknown"}},
    )
    assert out["intent"] == "unknown" and out["reply"]


async def test_graph_auto_approves_small_refund(session, seeded):
    llm = FakeLLM(['{"intent":"refund"}', "退款已提交"])
    graph = make_graph(session, llm)
    out = await graph.ainvoke(
        {"text": f"{seeded.paid_order_no} 退 50 元", "actor_role": "user",
         "actor_id": seeded.user_id, "merchant_id": None},
        config={"configurable": {"thread_id": "t-auto"}},
    )
    assert out["triggering_rule"] is None
    assert out["human_task_id"] is None
    assert out["refund_state"] == "refunded"


async def test_graph_interrupts_then_resumes(session, seeded):
    llm = FakeLLM(['{"intent":"refund"}', "已提交商家审核", "退款已受理"])
    graph = make_graph(session, llm)
    cfg = {"configurable": {"thread_id": "t-hitl"}}

    first = await graph.ainvoke(
        {"text": f"{seeded.shipped_order_no} 我要退款", "actor_role": "user",
         "actor_id": seeded.user_id, "merchant_id": None}, config=cfg)
    assert "__interrupt__" in first
    task_id = first["__interrupt__"][0].value["task_id"]

    second = await graph.ainvoke(Command(resume={"decision": "approved", "note": None}), config=cfg)
    assert second["human_task_id"] == task_id
    assert second["refund_state"] == "refunded"
    assert second["reply"]


async def test_graph_resume_with_missing_thread_raises(session, seeded):
    import pytest
    graph = make_graph(session, FakeLLM([]))
    with pytest.raises(Exception):
        await graph.ainvoke(Command(resume={"decision": "approved"}),
                            config={"configurable": {"thread_id": "never-started"}})
