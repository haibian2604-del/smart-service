from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class Product(PKMixin, TimestampMixin, Base):
    __tablename__ = "products"

    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column()
    category: Mapped[str | None] = mapped_column()
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    description: Mapped[str | None] = mapped_column()
