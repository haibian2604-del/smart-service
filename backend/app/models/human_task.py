from datetime import datetime
import enum

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Enum as SAEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin



class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HumanTask(PKMixin, TimestampMixin, Base):
    __tablename__ = "human_tasks"
    __table_args__ = (Index("ix_human_tasks_thread_id", "thread_id"),)

    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column()
    type: Mapped[str] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        default=TaskStatus.PENDING,
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column()
