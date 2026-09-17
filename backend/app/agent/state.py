from decimal import Decimal
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.agent.scope import Scope


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    actor_role: Literal["user", "merchant"]
    actor_id: int
    merchant_id: int | None
    text: str                        # 本轮用户输入
    intent: str
    order_no: str | None
    refund_amount: Decimal | None
    refund_draft: dict | None
    refund_state: str | None         # 对外可读终态：refunded / rejected / draft
    human_task_id: int | None
    human_decision: str | None
    human_note: str | None
    triggering_rule: str | None
    degraded: bool
    reply: str | None
    widgets: list[dict]


def new_state(*, scope: Scope, text: str) -> AgentState:
    return AgentState(
        actor_role=scope.role,
        actor_id=scope.user_id,
        merchant_id=scope.merchant_id,
        text=text,
    )
