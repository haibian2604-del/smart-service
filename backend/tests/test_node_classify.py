import pytest
from app.agent.nodes.classify import classify_node
from app.agent.scope import Scope
from app.agent.state import new_state
from tests.fakes import FakeLLM


async def test_classify_routes_order_intent():
    llm = FakeLLM(['{"intent":"order"}'])
    state = new_state(scope=Scope.for_user(1), text="我的订单到哪了")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "order"


async def test_classify_extracts_order_no_without_llm():
    llm = FakeLLM(['{"intent":"refund"}'])
    state = new_state(scope=Scope.for_user(1), text="订单 #A1002 我要退款")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "refund" and out["order_no"] == "#A1002"


@pytest.mark.parametrize("bad", ['{"intent":"没这个意图"}', "纯文本"])
async def test_classify_falls_back_to_unknown(bad):
    llm = FakeLLM([bad, bad])
    state = new_state(scope=Scope.for_user(1), text="??")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "unknown"


async def test_classify_falls_back_to_keyword_rule_when_llm_dead():
    """LLM 完全不可用时，关键词兜底保证 demo 不翻车。"""
    llm = FakeLLM(["垃圾输出", "垃圾输出"])
    state = new_state(scope=Scope.for_user(1), text="我要退款")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "refund"
    assert out["degraded"] is True


async def test_classify_uses_history_for_follow_up():
    llm = FakeLLM([])
    """追问「它到哪了」应结合历史识别为订单查询。"""
    from app.agent.state import new_state
    from app.agent.scope import Scope

    llm.responses = ['{"intent": "order"}']
    state = new_state(scope=Scope.for_user(1), text="它到哪了")
    state["history"] = [
        {"role": "user", "content": "降噪耳机 Pro 多少钱"},
        {"role": "assistant", "content": "降噪耳机 Pro 售价 399 元"},
        {"role": "user", "content": "它到哪了"},
    ]
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "order"
    system, user = llm.prompts[-1]
    assert "降噪耳机 Pro 多少钱" in user      # 历史进入提示词
    assert "当前消息：它到哪了" in user       # 当前消息单独标注
