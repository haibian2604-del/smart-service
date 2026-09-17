"""转人工确定性规则：判定在代码里，不让小模型碰。"""
from decimal import Decimal
from enum import Enum

from app.core.config import get_settings


class Trigger(str, Enum):
    USER_REQUESTED = "user_requested"
    ALREADY_SHIPPED = "already_shipped"
    AMOUNT_OVER_THRESHOLD = "amount_over_threshold"


USER_REQUEST_KEYWORDS = ("人工", "客服", "投诉", "转接")


def detect_human_trigger(*, order_status: str, refund_amount: Decimal,
                         user_text: str, threshold: Decimal | None = None) -> Trigger | None:
    """优先级：用户明确要求 > 已发货/已签收 > 金额超阈值。"""
    if any(k in user_text for k in USER_REQUEST_KEYWORDS):
        return Trigger.USER_REQUESTED
    if order_status in ("shipped", "delivered"):
        return Trigger.ALREADY_SHIPPED
    if refund_amount > (threshold if threshold is not None else get_settings().refund_amount_threshold):
        return Trigger.AMOUNT_OVER_THRESHOLD
    return None
