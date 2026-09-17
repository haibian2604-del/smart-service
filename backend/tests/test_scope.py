import pytest

from app.agent.scope import Scope


def test_user_scope_has_no_merchant():
    s = Scope.for_user(user_id=1)
    assert s.role == "user"
    assert s.merchant_id is None


def test_merchant_scope_requires_merchant_id():
    s = Scope.for_merchant(user_id=2, merchant_id=1)
    assert s.merchant_id == 1
    with pytest.raises(ValueError):
        Scope.for_merchant(user_id=2, merchant_id=None)
