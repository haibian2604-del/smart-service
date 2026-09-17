import enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class Conversation(PKMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column()


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class Message(PKMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column()
    content: Mapped[str | None] = mapped_column()
    widgets: Mapped[list | None] = mapped_column(JSONB)
    tool_calls: Mapped[list | None] = mapped_column(JSONB)
