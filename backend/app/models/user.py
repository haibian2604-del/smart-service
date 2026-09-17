import enum

from sqlalchemy import CheckConstraint, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class UserRole(str, enum.Enum):
    USER = "user"
    MERCHANT = "merchant"


class User(PKMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role = 'merchant' AND merchant_id IS NOT NULL) OR (role = 'user' AND merchant_id IS NULL)",
            name="ck_user_role_merchant",
        ),
    )

    name: Mapped[str] = mapped_column()
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e])
    )
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
