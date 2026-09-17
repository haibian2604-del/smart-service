import pytest

from app.api.deps import resolve_actor


async def test_resolve_customer(session, seeded):
    actor = await resolve_actor(session, x_actor_id=seeded.user_id)
    assert actor.role == "user" and actor.merchant_id is None


async def test_resolve_merchant(session, seeded):
    actor = await resolve_actor(session, x_actor_id=seeded.merchant_user_id)
    assert actor.role == "merchant" and actor.merchant_id == seeded.merchant_id


async def test_resolve_unknown_actor_raises_401(session):
    with pytest.raises(Exception) as e:
        await resolve_actor(session, x_actor_id=999999)
    assert "401" in str(e.value) or "actor_not_found" in str(e.value)


async def test_actor_exposes_scope(session, seeded):
    actor = await resolve_actor(session, x_actor_id=seeded.user_id)
    scope = actor.to_scope()
    assert scope.user_id == seeded.user_id and scope.role == "user"
