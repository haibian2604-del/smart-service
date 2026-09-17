import pytest
from pydantic import BaseModel

from app.agent.llm_json import ask_json, strip_code_fence
from tests.fakes import FakeLLM


class Intent(BaseModel):
    intent: str


def test_strip_code_fence_removes_json_fence():
    assert strip_code_fence('```json\n{"intent":"order"}\n```') == '{"intent":"order"}'


def test_strip_code_fence_leaves_plain_json_untouched():
    assert strip_code_fence('{"intent":"order"}') == '{"intent":"order"}'


async def test_ask_json_parses_clean_output():
    llm = FakeLLM(['{"intent":"order"}'])
    got = await ask_json(llm, system="s", user="u", schema=Intent)
    assert got.intent == "order"
    assert llm.calls == 1


async def test_ask_json_repairs_malformed_output():
    llm = FakeLLM(["```json\n{'intent': 'order',}\n```"])
    got = await ask_json(llm, system="s", user="u", schema=Intent)
    assert got.intent == "order"


async def test_ask_json_retries_once_then_fails():
    llm = FakeLLM(["完全不是 JSON", "也不是"])
    with pytest.raises(ValueError, match="llm_json_failed"):
        await ask_json(llm, system="s", user="u", schema=Intent, retries=1)
    assert llm.calls == 2


async def test_ask_json_validates_against_schema():
    llm = FakeLLM(['{"wrong":1}', '{"also_bad":2}'])
    with pytest.raises(ValueError, match="llm_json_failed"):
        await ask_json(llm, system="s", user="u", schema=Intent, retries=1)
    assert llm.calls == 2
