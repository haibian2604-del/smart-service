from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Scope:
    role: Literal["user", "merchant"]
    user_id: int
    merchant_id: int | None

    @classmethod
    def for_user(cls, user_id: int) -> "Scope":
        return cls(role="user", user_id=user_id, merchant_id=None)

    @classmethod
    def for_merchant(cls, user_id: int, merchant_id: int | None) -> "Scope":
        if merchant_id is None:
            raise ValueError("merchant scope requires merchant_id")
        return cls(role="merchant", user_id=user_id, merchant_id=merchant_id)
