from app.agent.nodes.order import order_node
from app.agent.nodes.product import product_node
from app.agent.scope import Scope
from app.agent.state import new_state
from tests.fakes import FakeLLM


async def test_product_node_returns_widget_and_reply(session, seeded):
    llm = FakeLLM(["为您找到以下商品"])
    state = new_state(scope=Scope.for_user(seeded.user_id), text="有耳机吗")
    state["intent"] = "product"
    out = await product_node(state, session=session, llm=llm)
    assert out["widgets"][0]["kind"] == "product_list"
    assert out["reply"]


async def test_order_node_missing_order_no_lists_my_orders(session, seeded):
    llm = FakeLLM(["您购买过蓝牙耳机和冲锋衣"])
    state = new_state(scope=Scope.for_user(seeded.user_id), text="我购买了哪些商品")
    state["intent"] = "order"
    out = await order_node(state, session=session, llm=llm)
    assert out["reply"] == "您购买过蓝牙耳机和冲锋衣"
    assert out["widgets"] and out["widgets"][0]["kind"] == "order"
    assert llm.calls == 1


async def test_order_node_emits_order_widget(session, seeded):
    llm = FakeLLM(["您的订单已发货"])
    state = new_state(scope=Scope.for_user(seeded.user_id), text=f"{seeded.order_no} 到哪了")
    state["intent"] = "order"
    state["order_no"] = seeded.order_no
    out = await order_node(state, session=session, llm=llm)
    assert out["widgets"][0]["data"]["order_no"] == seeded.order_no


async def test_order_node_handles_not_found(session, seeded):
    llm = FakeLLM([])
    state = new_state(scope=Scope.for_user(seeded.user_id), text="x")
    state["intent"] = "order"
    state["order_no"] = "#A9999"
    out = await order_node(state, session=session, llm=llm)
    assert "没有找到" in out["reply"]
