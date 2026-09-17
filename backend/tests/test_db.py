from sqlalchemy import text


async def test_session_can_execute(session):
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def test_session_rollback_isolates(session):
    await session.execute(text("CREATE TEMP TABLE t (v int)"))
    await session.execute(text("INSERT INTO t VALUES (1)"))
    assert (await session.execute(text("SELECT count(*) FROM t"))).scalar_one() == 1
