from datetime import datetime

from sqlalchemy import BigInteger, text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    pass


class PKMixin:
    @declared_attr
    def id(cls) -> Mapped[int]:
        return mapped_column(BigInteger, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
