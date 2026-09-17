from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Enum as SAEnum, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class RefundStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"


def _enum(cls):
    return SAEnum(cls, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e])


class Refund(PKMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending','approved','rejected','refunded')",
            name="ck_refund_status",
        ),
    )

    refund_no: Mapped[str] = mapped_column(unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[RefundStatus] = mapped_column(
        _enum(RefundStatus), default=RefundStatus.DRAFT
    )
    review_note: Mapped[str | None] = mapped_column()
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()
