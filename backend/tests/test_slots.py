import pytest
from app.agent.slots import extract_order_no, extract_refund_amount


@pytest.mark.parametrize("text,expected", [
    ("订单 #A1002 我要退款", "#A1002"),
    ("帮我退 a1002", "#A1002"),
    ("订单A1002的问题", "#A1002"),
    ("# A1002", "#A1002"),
    ("我要退款", None),
    ("#A100", None),
])
def test_extract_order_no(text, expected):
    assert extract_order_no(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("退款 199.00 元", "199.00"),
    ("退我￥89", "89"),
    ("全额退款", None),
])
def test_extract_refund_amount(text, expected):
    got = extract_refund_amount(text)
    assert (got is None and expected is None) or str(got) == expected
