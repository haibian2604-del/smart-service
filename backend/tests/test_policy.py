from decimal import Decimal
import pytest
from app.agent.policy import Trigger, detect_human_trigger


def test_user_explicit_request_wins():
    t = detect_human_trigger(order_status="paid", refund_amount=Decimal("1"),
                             user_text="我要人工客服")
    assert t is Trigger.USER_REQUESTED


@pytest.mark.parametrize("status", ["shipped", "delivered"])
def test_shipped_or_delivered_needs_human(status):
    assert detect_human_trigger(order_status=status, refund_amount=Decimal("1"),
                                user_text="退款") is Trigger.ALREADY_SHIPPED


def test_amount_over_threshold_needs_human():
    assert detect_human_trigger(order_status="paid", refund_amount=Decimal("200.01"),
                                user_text="退款") is Trigger.AMOUNT_OVER_THRESHOLD


def test_threshold_is_inclusive_at_boundary():
    assert detect_human_trigger(order_status="paid", refund_amount=Decimal("200.00"),
                                user_text="退款") is None


def test_small_paid_order_auto_approves():
    assert detect_human_trigger(order_status="paid", refund_amount=Decimal("199.99"),
                                user_text="不想要了") is None
