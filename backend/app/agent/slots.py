"""槽位抽取：纯正则，不依赖模型。抽不到返回 None，由节点追问。"""
import re
from decimal import Decimal

ORDER_NO_RE = re.compile(r"#?\s*[Aa](\d{4})(?!\d)")
AMOUNT_RE = re.compile(r"[￥¥]\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:元|块)")


def extract_order_no(text: str) -> str | None:
    m = ORDER_NO_RE.search(text)
    return f"#A{m.group(1)}" if m else None


def extract_refund_amount(text: str) -> Decimal | None:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    return Decimal(m.group(1) or m.group(2))
