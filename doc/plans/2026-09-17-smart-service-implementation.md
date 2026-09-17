# 智能客服 Agent 系统 — 实施计划

> **For implementer:** Use TDD throughout. Write failing test first. Watch it fail. Then implement.
> 本文件只定义任务、验收标准与执行顺序，不含最终代码。设计依据见 `doc/ARCHITECTURE.md`。

**Goal:** 交付一个可本地运行、可演示的智能客服 Agent 系统 —— 用户端能查商品、查订单、申请退款；退款触发规则时挂起为人工工单，由商家端审批后恢复图执行并答复用户。

**Architecture:** FastAPI 提供 SSE 对话流与业务 REST；LangGraph `StateGraph` 承载意图路由 → 工具节点 → 人工中断 → 响应生成；`AsyncPostgresSaver` 持久化 checkpoint，使 `interrupt()` 挂起后可由商家审批动作恢复。租户隔离（`merchant_id`）下沉到工具层，LLM 只负责意图分类与语言组织。

**Tech Stack:** Python 3.13 · uv · FastAPI · SQLAlchemy 2.x（async）· Alembic · PostgreSQL 16 · LangGraph + langgraph-checkpoint-postgres · langchain-openai · json-repair · pytest + pytest-asyncio · Vite · React 19 · TypeScript · Tailwind CSS v4 · Vitest

**测试策略：**

| 层 | 工具 | 说明 |
|---|---|---|
| 后端单测 | pytest + pytest-asyncio | 每个测试跑在独立事务里，结束回滚 |
| DB | 真实 PostgreSQL（docker compose） | LangGraph checkpointer 依赖 PG，不用 sqlite 替代 |
| LLM | `FakeLLM` 存根 | 测试**永不**调用 oMLX，网络无关、结果确定 |
| API | httpx `ASGITransport` | 不起真实端口 |
| 前端 | Vitest + Testing Library + jsdom | 只测纯逻辑与组件渲染，不测样式 |

**前置条件：** Docker 可用；`uv` 已安装（0.11.26）；Node ≥ 22。

**目录约定：** 本仓库文档统一放 `doc/` 下（覆盖 skill 默认的 `docs/`），本计划位于 `doc/plans/`。

---

## 阶段总览

| 阶段 | Tasks | 产出 |
|---|---|---|
| P0 脚手架 | 1–4 | 可启动的后端骨架 + 测试基线 + PG 容器 |
| P1 数据层 | 5–8 | 9 张 ORM 表 + 迁移 + 种子数据 |
| P2 工具层 | 9–12 | 7 个纯函数工具，含越权测试，**不接 LLM** |
| P3 Agent 图 | 13–19 | 完整图 + 中断恢复，全程 FakeLLM 覆盖 |
| P4 API 层 | 20–23 | 鉴权、SSE、轮询、审批接口 |
| P5 前端 | 24–30 | `/chat` 对话页 + `/merchant` 审批台 |
| P6 串通 | 31–32 | 端到端演示测试 + 启动脚本 |

---

## Phase 0 · 脚手架

### Task 1: 初始化仓库与 uv 项目

**Files:**
- Create: `.gitignore`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_health.py
from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

**Step 2: 确认失败**

```bash
cd /Users/kk/code/project/smart_service
git init
printf '%s\n' '__pycache__/' '*.pyc' '.venv/' '.env' 'node_modules/' 'dist/' > .gitignore
cd backend && uv init --bare --python 3.13 && uv add fastapi "uvicorn[standard]" httpx
uv add --dev pytest pytest-asyncio
uv run pytest tests/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

**Step 3: 最小实现**

`backend/pyproject.toml` 追加：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

`backend/app/main.py`：

```python
from fastapi import FastAPI

app = FastAPI(title="Smart Service Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

**Step 4: 确认通过**

```bash
cd /Users/kk/code/project/smart_service/backend && uv run pytest tests/test_health.py -v
```

Expected: PASS — `1 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "chore: init repo and fastapi skeleton"
```

---

### Task 2: 配置层

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/.env.example`
- Test: `backend/tests/test_config.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_config.py
from app.core.config import Settings


def test_settings_have_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.llm_base_url.endswith("/v1")
    assert s.llm_model == "gemma-4-e2b-it-4bit"
    assert s.refund_amount_threshold == 200


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    s = Settings(_env_file=None)
    assert s.llm_model == "custom-model"
```

**Step 2: 确认失败**

```bash
uv add pydantic-settings
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.config'`

**Step 3: 最小实现**

```python
# backend/app/core/config.py
from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/smart_service"
    test_database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/smart_service_test"
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "gemma-4-e2b-it-4bit"
    llm_api_key: str = "none"
    refund_amount_threshold: Decimal = Decimal("200")
    demo_user_id: int = 1
    demo_merchant_ids: tuple[int, ...] = (1, 2)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/.env.example` 写入同名变量的示例值。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS — `2 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(config): add settings layer"
```

---

### Task 3: PostgreSQL 容器与异步 DB 层

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/app/core/db.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_db.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_db.py
from sqlalchemy import text


async def test_session_can_execute(session):
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def test_session_rollback_isolates(session):
    await session.execute(text("CREATE TEMP TABLE t (v int)"))
    await session.execute(text("INSERT INTO t VALUES (1)"))
    assert (await session.execute(text("SELECT count(*) FROM t"))).scalar_one() == 1
```

**Step 2: 确认失败**

```bash
cd /Users/kk/code/project/smart_service
docker compose up -d
docker compose exec -T db psql -U postgres -c "CREATE DATABASE smart_service_test;"
cd backend && uv add "sqlalchemy[asyncio]" asyncpg
uv run pytest tests/test_db.py -v
```

Expected: FAIL — `fixture 'session' not found`

**Step 3: 最小实现**

`docker-compose.yml`（仓库根目录）：

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: smart_service
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

```python
# backend/app/core/db.py
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with maker() as session:
        yield session
```

```python
# backend/tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(get_settings().test_database_url, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    conn = await engine.connect()
    trans = await conn.begin()
    sess = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield sess
    finally:
        await sess.close()
        await trans.rollback()
        await conn.close()
```

> 每个测试独占一个事务，结束后回滚 —— 测试间零污染，且无需重建表。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_db.py -v
```

Expected: PASS — `2 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(db): add postgres compose and async session layer"
```

---

### Task 4: Alembic 初始化

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/`
- Test: `backend/tests/test_alembic.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_alembic.py
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_config_points_to_metadata():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == () or len(script.get_heads()) == 1
```

**Step 2: 确认失败**

```bash
uv add alembic
uv run pytest tests/test_alembic.py -v
```

Expected: FAIL — `CommandError: Path doesn't exist: alembic`

**Step 3: 最小实现**

```bash
uv run alembic init alembic
```

改写 `backend/alembic/env.py` 为异步模式：从 `app.models.base.Base.metadata` 取 `target_metadata`，用 `settings.database_url` 覆盖 `sqlalchemy.url`，`run_migrations_online()` 内使用 `async_engine_from_config` + `connection.run_sync(do_run_migrations)`。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_alembic.py -v
```

Expected: PASS — `1 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "chore(alembic): init async migration env"
```

---

## Phase 1 · 数据层

### Task 5: ORM Base 与租户/用户模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/merchant.py`
- Create: `backend/app/models/user.py`
- Test: `backend/tests/test_models_core.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_models_core.py
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Merchant, User, UserRole


async def test_create_merchant_and_merchant_user(session):
    m = Merchant(name="商家 A", slug="merchant-a")
    session.add(m)
    await session.flush()
    u = User(name="A 店客服", role=UserRole.MERCHANT, merchant_id=m.id)
    session.add(u)
    await session.flush()
    assert u.merchant_id == m.id
    assert u.role is UserRole.MERCHANT


async def test_merchant_slug_is_unique(session):
    session.add_all([Merchant(name="A", slug="dup"), Merchant(name="B", slug="dup")])
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_merchant_role_requires_merchant_id(session):
    session.add(User(name="无租户商家", role=UserRole.MERCHANT, merchant_id=None))
    with pytest.raises(IntegrityError):
        await session.flush()
```

**Step 2: 确认失败**

```bash
uv run pytest tests/test_models_core.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

**Step 3: 最小实现**

`base.py` 定义 `Base(DeclarativeBase)`、`TimestampMixin`（`created_at` server_default `now()`）、`PKMixin`（`id` BigInteger identity primary key）。

`merchant.py`：`Merchant` —— `name: Mapped[str]`、`slug: Mapped[str]`（`unique=True`）。

`user.py`：`UserRole(str, Enum)` = `USER="user"` / `MERCHANT="merchant"`；`User` —— `name`、`role`、`merchant_id: Mapped[int | None]`（FK `merchants.id`）、表级约束：

```python
__table_args__ = (
    CheckConstraint(
        "(role = 'merchant' AND merchant_id IS NOT NULL) OR (role = 'user' AND merchant_id IS NULL)",
        name="ck_user_role_merchant",
    ),
)
```

`models/__init__.py` 导出全部模型，供 `base.Base.metadata` 收集。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_models_core.py -v
```

Expected: PASS — `3 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(models): add merchant and user with tenant constraint"
```

---

### Task 6: 商品与订单模型

**Files:**
- Create: `backend/app/models/product.py`
- Create: `backend/app/models/order.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_catalog.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_models_catalog.py
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Order, OrderItem, OrderStatus, Product


async def test_product_belongs_to_merchant(session, seeded):
    p = Product(merchant_id=seeded.merchant_id, name="降噪耳机",
                category="数码", price=Decimal("599.00"), stock=10)
    session.add(p)
    await session.flush()
    assert p.merchant_id == seeded.merchant_id


async def test_order_no_is_unique(session, seeded):
    dup = Order(order_no=seeded.order_no, user_id=seeded.user_id,
                merchant_id=seeded.merchant_id, status=OrderStatus.PAID,
                total_amount=Decimal("199.00"))
    session.add(dup)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_order_status_is_constrained(session, seeded):
    bad = Order(order_no="#A9998", user_id=seeded.user_id,
                merchant_id=seeded.merchant_id, status="not_a_status",
                total_amount=Decimal("1.00"))
    session.add(bad)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_order_item_links_product(session, seeded):
    item = OrderItem(order_id=seeded.order_id, product_id=seeded.product_id,
                     quantity=2, unit_price=Decimal("89.00"))
    session.add(item)
    await session.flush()
    assert item.quantity == 2
```

**Step 2: 确认失败**

```bash
uv run pytest tests/test_models_catalog.py -v
```

Expected: FAIL — `ImportError: cannot import name 'Order'`

**Step 3: 最小实现**

`product.py`：`Product` —— `merchant_id` FK 非空、`name`、`category: Mapped[str | None]`、`price: Numeric(10,2)`、`stock: int`、`description: Mapped[str | None]`。

`order.py`：
- `OrderStatus(str, Enum)` = `PENDING/PAID/SHIPPED/DELIVERED/CANCELLED`，`Order.status` 上加 `CheckConstraint` 枚举值
- `Order` —— `order_no` unique、`user_id` FK、`merchant_id` FK、`status`、`total_amount: Numeric(10,2)`、`shipped_at` / `delivered_at` 可空、`shipped_at` 与 `status=SHIPPED` 的一致性由服务层保证（不在 DB 层约束）
- `OrderItem` —— `order_id` FK、`product_id` FK、`quantity`、`unit_price: Numeric(10,2)`

`conftest.py` 新增 `seeded` fixture，返回 `SimpleNamespace`。**后续多个 Task 都依赖它，字段需一次定义齐全：**

| 字段 | 含义 |
|---|---|
| `merchant_id` / `other_merchant_id` | 两个租户 |
| `merchant_user_id` / `other_merchant_user_id` | 两个商家账号 |
| `user_id` | 演示用户 |
| `user_order_count` | 该用户的订单总数 |
| `order_id` / `order_no` | 商家 A 的一个 `paid` 订单 |
| `paid_order_no` | 商家 A · `paid` · 小额可自动通过 |
| `shipped_order_no` | 商家 A · `shipped` · 大额 |
| `cancelled_order_no` | 商家 A · `cancelled` |
| `product_id` | 商家 A 的一个商品 |
| `draft_refund_id` | 一条 `status=draft` 的退款单 |

fixture 内直接构造 ORM 对象并 `flush()`，**不复用 `scripts/seed.py`** —— 单测要的是最小可控数据集，种子脚本是给演示用的，两者职责不同。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_models_catalog.py -v
```

Expected: PASS — `4 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(models): add product, order and order_item"
```

---

### Task 7: 退款 / 会话 / 工单模型

**Files:**
- Create: `backend/app/models/refund.py`
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/human_task.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_refund.py`

**Step 1: 写失败的测试**

```python
# backend/app/models/refund.py 对应的测试
from decimal import Decimal

from app.models import HumanTask, Message, Refund, RefundStatus, TaskStatus


async def test_refund_status_defaults_to_draft(session, seeded):
    r = Refund(refund_no="#R2001", order_id=seeded.order_id, user_id=seeded.user_id,
               merchant_id=seeded.merchant_id, reason="不想要了",
               amount=Decimal("199.00"))
    session.add(r)
    await session.flush()
    assert r.status is RefundStatus.DRAFT


async def test_human_task_links_thread(session, seeded):
    t = HumanTask(merchant_id=seeded.merchant_id, thread_id="conv-1",
                  type="refund_review", payload={"order_no": "#A1001"})
    session.add(t)
    await session.flush()
    assert t.status is TaskStatus.PENDING
    assert t.payload["order_no"] == "#A1001"


async def test_message_stores_widgets(session):
    m = Message(conversation_id=1, role="assistant", content="订单已发货",
                widgets=[{"kind": "order", "data": {"order_no": "#A1001"}}])
    session.add(m)
    await session.flush()
    assert m.widgets[0]["kind"] == "order"
```

**Step 2: 确认失败**

Expected: FAIL — `ImportError: cannot import name 'Refund'`

**Step 3: 最小实现**

- `RefundStatus(str, Enum)` = `DRAFT/PENDING/APPROVED/REJECTED/REFUNDED`
- `Refund` —— `refund_no` unique、`order_id` / `user_id` / `merchant_id` 三个 FK 全非空、`reason: Mapped[str | None]`、`amount`、`status` 默认 `DRAFT`、`review_note`、`reviewed_by` FK 可空、`reviewed_at` 可空
- `Conversation` —— `user_id` FK、`title` 可空
- `Message` —— `conversation_id` FK、`role: Mapped[str]`、`content: Mapped[str | None]`、`widgets: Mapped[list | None] = mapped_column(JSONB)`、`tool_calls: Mapped[list | None] = mapped_column(JSONB)`
- `TaskStatus(str, Enum)` = `PENDING/APPROVED/REJECTED`
- `HumanTask` —— `merchant_id` FK 非空、`thread_id: Mapped[str]`（索引）、`type`、`payload: Mapped[dict] = mapped_column(JSONB)`、`status` 默认 `PENDING`、`assignee_id` FK 可空、`resolved_at` 可空

**Step 4: 确认通过**

```bash
uv run pytest tests/test_models_refund.py -v
```

Expected: PASS — `3 passed`

**Step 5: 生成迁移并提交**

```bash
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
git add -A && git commit -m "feat(models): add refund, conversation, message, human_task"
```

---

### Task 8: 种子数据脚本

**Files:**
- Create: `backend/scripts/seed.py`
- Test: `backend/tests/test_seed.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_seed.py
from sqlalchemy import func, select

from app.models import Merchant, Order, OrderStatus, Product, User
from scripts.seed import seed


async def test_seed_is_idempotent(session):
    await seed(session)
    first = (await session.execute(select(func.count(Merchant.id)))).scalar_one()
    await seed(session)
    second = (await session.execute(select(func.count(Merchant.id)))).scalar_one()
    assert first == second == 2


async def test_seed_covers_all_order_statuses(session):
    await seed(session)
    rows = (await session.execute(select(Order.status).distinct())).scalars().all()
    assert {OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.PAID} <= set(rows)


async def test_seed_creates_demo_user_and_merchant_accounts(session):
    await seed(session)
    users = (await session.execute(select(User))).scalars().all()
    assert sum(u.role.value == "user" for u in users) == 1
    assert sum(u.role.value == "merchant" for u in users) == 2


async def test_seed_products_belong_to_merchants(session):
    await seed(session)
    products = (await session.execute(select(Product))).scalars().all()
    assert len(products) >= 12
    assert all(p.merchant_id in (1, 2) for p in products)
```

**Step 2: 确认失败**

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.seed'`

**Step 3: 最小实现**

`seed(session)` 幂等实现：按 `slug` upsert `merchants`，按 `name` upsert `users` / `products`，订单按 `order_no` upsert。

固定数据：
- 商家：`merchant-a`「青柠数码」、`merchant-b`「山野户外」
- 用户：`演示用户`（`role=user`）；两个商家客服账号（各绑一个商家）
- 商品：每商家 6 个，覆盖数码与户外两类
- 订单：8 条，`order_no` 从 `#A1001` 起
  - `#A1001` 商家 A · `paid` · ¥199.00 ← 演示自动通过
  - `#A1002` 商家 A · `shipped` · ¥599.00 ← 演示金额+已发货双触发
  - `#A1003` 商家 B · `delivered` · ¥89.00
  - 其余覆盖 `paid` / `shipped` / `delivered` / `cancelled`
- 每个商品各建 1 条 `order_items`

**Step 4: 确认通过**

```bash
uv run pytest tests/test_seed.py -v
```

Expected: PASS — `4 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(seed): add idempotent demo data seeder"
```

---

## Phase 2 · 工具层（不接 LLM）

> 本阶段全部工具是纯 async 函数，接收显式 `Scope`。**先把数据正确性验证到位，再引入 LLM。**

### Task 9: Scope 定义与工具契约

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/scope.py`
- Create: `backend/app/agent/tools/__init__.py`
- Create: `backend/app/agent/tools/registry.py`
- Test: `backend/tests/test_scope.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_scope.py
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


def test_registry_exposes_all_tools():
    from app.agent.tools.registry import TOOLS
    assert set(TOOLS) == {
        "search_products", "get_product_detail",
        "list_my_orders", "get_order_detail",
        "check_refund_policy", "create_refund_draft", "submit_refund",
    }
```

**Step 2: 确认失败**

Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent'`

**Step 3: 最小实现**

```python
# backend/app/agent/scope.py
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
```

`registry.py` 用 dict 汇总工具函数，键为工具名，供 JSON dispatch 查表。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_scope.py -v
```

Expected: PASS — `3 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(agent): add scope and tool registry"
```

---

### Task 10: 商品工具

**Files:**
- Create: `backend/app/agent/tools/products.py`
- Test: `backend/tests/test_tools_products.py`

**Step 1: 写失败的测试**

```python
# backend/app/agent/tools/products.py 的测试
from app.agent.scope import Scope
from app.agent.tools.products import get_product_detail, search_products


async def test_search_by_keyword(session, seeded):
    res = await search_products(session, Scope.for_user(seeded.user_id), keyword="耳机")
    assert len(res) >= 1
    assert all("耳机" in p["name"] for p in res)


async def test_search_returns_unit_price_as_str(session, seeded):
    res = await search_products(session, Scope.for_user(seeded.user_id), keyword="耳机")
    assert isinstance(res[0]["price"], str)  # Decimal 必须序列化，避免 JSON 精度丢失


async def test_search_empty_keyword_returns_top_n(session, seeded):
    res = await search_products(session, Scope.for_user(seeded.user_id), keyword=None, limit=5)
    assert len(res) == 5


async def test_product_detail_not_found_returns_none(session, seeded):
    assert await get_product_detail(session, Scope.for_user(seeded.user_id), product_id=99999) is None
```

**Step 2: 确认失败**

Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.tools.products'`

**Step 3: 最小实现**

```python
async def search_products(session, scope: Scope, keyword: str | None, limit: int = 5) -> list[dict]
async def get_product_detail(session, scope: Scope, product_id: int) -> dict | None
```

- 商品是**平台公开信息**，两个角色都可查，不做 tenant 过滤
- 关键词匹配 `name ILIKE %kw%` 或 `category ILIKE %kw%`
- 返回 dict，`price` 用 `str(Decimal)`，避免浮点误差

**Step 4: 确认通过**

```bash
uv run pytest tests/test_tools_products.py -v
```

Expected: PASS — `4 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(tools): add product search and detail"
```

---

### Task 11: 订单工具（含越权测试）

**Files:**
- Create: `backend/app/agent/tools/orders.py`
- Test: `backend/tests/test_tools_orders.py`

**Step 1: 写失败的测试**

```python
from sqlalchemy import select
from app.models import User, UserRole
from app.agent.scope import Scope
from app.agent.tools.orders import get_order_detail, list_my_orders


async def test_user_sees_only_own_orders(session, seeded):
    res = await list_my_orders(session, Scope.for_user(seeded.user_id))
    order_nos = {o["order_no"] for o in res}
    assert seeded.order_no in order_nos
    assert len(res) == seeded.user_order_count


async def test_user_cannot_read_others_order(session, seeded):
    other = User(name="别人", role=UserRole.USER)
    session.add(other)
    await session.flush()
    assert await get_order_detail(session, Scope.for_user(other.id), order_no=seeded.order_no) is None


async def test_merchant_sees_only_own_tenant_orders(session, seeded):
    scope = Scope.for_merchant(seeded.merchant_user_id, seeded.merchant_id)
    res = await list_my_orders(session, scope)
    assert res and all(o["merchant_id"] == seeded.merchant_id for o in res)


async def test_merchant_cannot_read_other_tenant_order(session, seeded):
    """关键越权测试：商家 B 查商家 A 的订单必须拿不到。"""
    scope_b = Scope.for_merchant(seeded.other_merchant_user_id, seeded.other_merchant_id)
    assert await get_order_detail(session, scope_b, order_no=seeded.order_no) is None


async def test_order_detail_includes_items(session, seeded):
    detail = await get_order_detail(session, Scope.for_user(seeded.user_id), order_no=seeded.order_no)
    assert detail["items"] and detail["items"][0]["quantity"] >= 1
```

**Step 2: 确认失败**

Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.tools.orders'`

**Step 3: 最小实现**

```python
def _scope_filter(scope: Scope):
    return Order.user_id == scope.user_id if scope.role == "user" else Order.merchant_id == scope.merchant_id

async def list_my_orders(session, scope: Scope) -> list[dict]
async def get_order_detail(session, scope: Scope, order_no: str) -> dict | None
```

- **两个函数都必须套用 `_scope_filter`**，`get_order_detail` 在 where 条件里就带上 scope，而不是先查后校验
- `order_no` 统一规范化为 `#A####` 大写形式再查
- 返回含 `status`、`total_amount`、`created_at`、`shipped_at`、`items[]`

> 这是本项目最容易出安全漏洞的地方。若只在 API 层过滤而工具层裸查，Agent 可以直接读到别家订单。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_tools_orders.py -v
```

Expected: PASS — `5 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(tools): add scoped order tools with tenant isolation tests"
```

---

### Task 12: 退款工具

**Files:**
- Create: `backend/app/agent/tools/refunds.py`
- Test: `backend/tests/test_tools_refunds.py`

**Step 1: 写失败的测试**

```python
from decimal import Decimal

from app.agent.scope import Scope
from app.agent.tools.refunds import check_refund_policy, create_refund_draft, submit_refund
from app.models import Refund, RefundStatus
from sqlalchemy import select


async def test_policy_marks_shipped_order_needs_human(session, seeded):
    r = await check_refund_policy(
        session, Scope.for_user(seeded.user_id),
        order_no=seeded.shipped_order_no, refund_amount=Decimal("599.00"),
        user_text="我要退款",
    )
    assert r["eligible"] is True
    assert r["trigger"] == "already_shipped"


async def test_policy_marks_small_paid_order_auto(session, seeded):
    r = await check_refund_policy(
        session, Scope.for_user(seeded.user_id),
        order_no=seeded.paid_order_no, refund_amount=Decimal("50.00"),
        user_text="不想要了",
    )
    assert r["trigger"] is None


async def test_policy_rejects_non_refundable_status(session, seeded):
    r = await check_refund_policy(
        session, Scope.for_user(seeded.user_id),
        order_no=seeded.cancelled_order_no, refund_amount=Decimal("10.00"),
        user_text="退款",
    )
    assert r["eligible"] is False


async def test_policy_respects_scope(session, seeded):
    scope_b = Scope.for_merchant(seeded.other_merchant_user_id, seeded.other_merchant_id)
    r = await check_refund_policy(session, scope_b, order_no=seeded.order_no,
                                  refund_amount=Decimal("10.00"), user_text="退款")
    assert r["eligible"] is False and r["reason"] == "order_not_found"


async def test_create_draft_then_submit_advances_status(session, seeded):
    policy = await check_refund_policy(session, Scope.for_user(seeded.user_id),
                                       order_no=seeded.paid_order_no,
                                       refund_amount=Decimal("50.00"), user_text="不想要了")
    draft = await create_refund_draft(session, Scope.for_user(seeded.user_id), policy=policy)
    assert draft["status"] == RefundStatus.DRAFT.value

    await submit_refund(session, Scope.for_user(seeded.user_id),
                        refund_id=draft["id"], decision="approved", note=None)
    row = (await session.execute(select(Refund).where(Refund.id == draft["id"]))).scalar_one()
    assert row.status is RefundStatus.REFUNDED


async def test_submit_rejected_records_note(session, seeded):
    policy = await check_refund_policy(session, Scope.for_user(seeded.user_id),
                                       order_no=seeded.paid_order_no,
                                       refund_amount=Decimal("50.00"), user_text="不想要了")
    draft = await create_refund_draft(session, Scope.for_user(seeded.user_id), policy=policy)
    await submit_refund(session, Scope.for_user(seeded.user_id),
                        refund_id=draft["id"], decision="rejected", note="超出退款期限")
    row = (await session.execute(select(Refund).where(Refund.id == draft["id"]))).scalar_one()
    assert row.status is RefundStatus.REJECTED and row.review_note == "超出退款期限"
```

**Step 2: 确认失败**

Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.tools.refunds'`

**Step 3: 最小实现**

```python
async def check_refund_policy(session, scope: Scope, *, order_no: str,
                              refund_amount: Decimal, user_text: str) -> dict
async def create_refund_draft(session, scope: Scope, *, policy: dict) -> dict
async def submit_refund(session, scope: Scope, *, refund_id: int,
                        decision: str, note: str | None) -> dict
```

- `check_refund_policy` 内部调用任务 13 的 `detect_human_trigger`，导出 `trigger` 供图路由
- 不可退状态集合：`cancelled`、已有 `pending/approved/refunded` 退款的订单
- `refund_no` 生成规则：`#R{2000 + 自增}`
- `create_refund_draft` 写 `status=DRAFT`；`submit_refund` 按 decision 写 `APPROVED→REFUNDED` 或 `REJECTED`，并记录 `reviewed_at`

**Step 4: 确认通过**

```bash
uv run pytest tests/test_tools_refunds.py -v
```

Expected: PASS — `6 passed`

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(tools): add refund policy, draft and submit"
```

---

## Phase 3 · Agent 图

### Task 13: 正则槽位抽取

**Files:**
- Create: `backend/app/agent/slots.py`
- Test: `backend/tests/test_slots.py`

**Step 1: 写失败的测试**

```python
# backend/app/agent/slots.py 的测试
import pytest
from app.agent.slots import extract_order_no, extract_refund_amount


@pytest.mark.parametrize("text,expected", [
    ("订单 #A1002 我要退款", "#A1002"),
    ("帮我退 a1002", "#A1002"),
    ("订单A1002的问题", "#A1002"),
    ("# A1002", "#A1002"),
    ("我要退款", None),
    ("#A100", None),
])
def test_extract_order_no(text, expected):
    assert extract_order_no(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("退款 199.00 元", "199.00"),
    ("退我￥89", "89"),
    ("全额退款", None),
])
def test_extract_refund_amount(text, expected):
    got = extract_refund_amount(text)
    assert (got is None and expected is None) or str(got) == expected
```

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.agent.slots'`

**Step 3: 最小实现**

```python
ORDER_NO_RE = re.compile(r"#?\s*[Aa](\d{4})(?!\d)")
AMOUNT_RE = re.compile(r"(?:￥|¥|\b)(\d+(?:\.\d{1,2})?)\s*(?:元|块)?")


def extract_order_no(text: str) -> str | None:
    m = ORDER_NO_RE.search(text)
    return f"#A{m.group(1)}" if m else None


def extract_refund_amount(text: str) -> Decimal | None:
    m = AMOUNT_RE.search(text)
    return Decimal(m.group(1)) if m else None
```

> 抽不到的槽位一律返回 `None`，由节点转而向用户追问 —— **不把这个任务交给小模型**。

**Step 4: 确认通过** → `uv run pytest tests/test_slots.py -v` → PASS — `9 passed`

**Step 5: 提交** → `git commit -m "feat(agent): add regex slot extraction"`

---

### Task 14: 转人工确定性规则

**Files:**
- Create: `backend/app/agent/policy.py`
- Test: `backend/tests/test_policy.py`

**Step 1: 写失败的测试**

```python
# backend/app/agent/policy.py 的测试
from decimal import Decimal
import pytest
from app.agent.policy import Trigger, detect_human_trigger


def test_user_explicit_request_wins():
    t = detect_human_trigger(order_status="paid", refund_amount=Decimal("1"),
                             user_text="我要人工客服")
    assert t is Trigger.USER_REQUESTED


@pytest.mark.parametrize("status", ["shipped", "delivered"])
def test_shipped_or_delivered_needs_human(status):
    assert detect_human_trigger(order_status=status, refund_amount=Decimal("1"),
                                user_text="退款") is Trigger.ALREADY_SHIPPED


def test_amount_over_threshold_needs_human():
    assert detect_human_trigger(order_status="paid", refund_amount=Decimal("200.01"),
                                user_text="退款") is Trigger.AMOUNT_OVER_THRESHOLD


def test_threshold_is_inclusive_at_boundary():
    assert detect_human_trigger(order_status="paid", refund_amount=Decimal("200.00"),
                                user_text="退款") is None


def test_small_paid_order_auto_approves():
    assert detect_human_trigger(order_status="paid", refund_amount=Decimal("199.99"),
                                user_text="不想要了") is None
```

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.agent.policy'`

**Step 3: 最小实现**

```python
class Trigger(str, Enum):
    USER_REQUESTED = "user_requested"
    ALREADY_SHIPPED = "already_shipped"
    AMOUNT_OVER_THRESHOLD = "amount_over_threshold"


USER_REQUEST_KEYWORDS = ("人工", "客服", "投诉", "转接")


def detect_human_trigger(*, order_status: str, refund_amount: Decimal,
                         user_text: str, threshold: Decimal | None = None) -> Trigger | None:
    if any(k in user_text for k in USER_REQUEST_KEYWORDS):
        return Trigger.USER_REQUESTED
    if order_status in ("shipped", "delivered"):
        return Trigger.ALREADY_SHIPPED
    if refund_amount > (threshold if threshold is not None else get_settings().refund_amount_threshold):
        return Trigger.AMOUNT_OVER_THRESHOLD
    return None
```

判定优先级：**用户明确要求 > 已发货/已签收 > 金额超阈值**。顺序即语义，测试已固化。

**Step 4: 确认通过** → PASS — `7 passed`
**Step 5: 提交** → `git commit -m "feat(agent): add deterministic human-handoff rules"`

---

### Task 15: LLM 客户端与 JSON 修复层

**Files:**
- Create: `backend/app/core/llm.py`
- Create: `backend/app/agent/llm_json.py`
- Create: `backend/tests/fakes.py`
- Test: `backend/tests/test_llm_json.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_llm_json.py
import pytest
from pydantic import BaseModel

from app.agent.llm_json import ask_json, strip_code_fence
from tests.fakes import FakeLLM


class Intent(BaseModel):
    intent: str


def test_strip_code_fence_removes_json_fence():
    assert strip_code_fence('```json\n{"intent":"order"}\n```') == '{"intent":"order"}'


def test_strip_code_fence_leaves_plain_json_untouched():
    assert strip_code_fence('{"intent":"order"}') == '{"intent":"order"}'


async def test_ask_json_parses_clean_output():
    llm = FakeLLM(['{"intent":"order"}'])
    got = await ask_json(llm, system="s", user="u", schema=Intent)
    assert got.intent == "order"
    assert llm.calls == 1


async def test_ask_json_repairs_malformed_output():
    llm = FakeLLM(["```json\n{'intent': 'order',}\n```"])
    got = await ask_json(llm, system="s", user="u", schema=Intent)
    assert got.intent == "order"


async def test_ask_json_retries_once_then_fails():
    llm = FakeLLM(["完全不是 JSON", "也不是"])
    with pytest.raises(ValueError, match="llm_json_failed"):
        await ask_json(llm, system="s", user="u", schema=Intent, retries=1)
    assert llm.calls == 2


async def test_ask_json_validates_against_schema():
    llm = FakeLLM(['{"intent":"order"}', '{"wrong":1}'])
    with pytest.raises(ValueError, match="llm_json_failed"):
        await ask_json(llm, system="s", user="u", schema=Intent, retries=1)
```

**Step 2: 确认失败**

```bash
uv add langchain-core langchain-openai json-repair
uv run pytest tests/test_llm_json.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent.llm_json'`

**Step 3: 最小实现**

`core/llm.py`：

```python
class LLMClient(Protocol):
    async def complete(self, system: str, user: str) -> str: ...
    def stream(self, system: str, user: str) -> AsyncIterator[str]: ...


class OMLXClient:
    """走 OpenAI 兼容接口，ChatOpenAI(base_url=settings.llm_base_url)."""
    ...


def get_llm() -> LLMClient: ...   # 进程内单例，测试中 monkeypatch
```

`agent/llm_json.py`：

```python
def strip_code_fence(text: str) -> str
async def ask_json(llm, *, system: str, user: str, schema: type[BaseModel],
                   retries: int = 1) -> BaseModel
```

流程：`complete()` → `strip_code_fence()` → `json_repair.loads()` → `schema.model_validate()`；任一步失败则带**纠错提示**重试，重试耗尽抛 `ValueError("llm_json_failed")`。

`tests/fakes.py`：

```python
class FakeLLM:
    def __init__(self, responses: list[str]): self._responses = responses; self.calls = 0
    async def complete(self, system: str, user: str) -> str: ...
    async def stream(self, system: str, user: str): yield ...
```

**Step 4: 确认通过**

```bash
uv run pytest tests/test_llm_json.py -v
```

Expected: PASS — `6 passed`

**Step 5: 提交** → `git commit -m "feat(agent): add llm client and json repair layer"`

---

### Task 16: AgentState 与 classify 节点

**Files:**
- Create: `backend/app/agent/state.py`
- Create: `backend/app/agent/prompts/__init__.py`
- Create: `backend/app/agent/prompts/classify.py`
- Create: `backend/app/agent/nodes/__init__.py`
- Create: `backend/app/agent/nodes/classify.py`
- Test: `backend/tests/test_node_classify.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_node_classify.py
import pytest
from app.agent.nodes.classify import classify_node
from app.agent.scope import Scope
from app.agent.state import new_state
from tests.fakes import FakeLLM


async def test_classify_routes_order_intent():
    llm = FakeLLM(['{"intent":"order"}'])
    state = new_state(scope=Scope.for_user(1), text="我的订单到哪了")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "order"


async def test_classify_extracts_order_no_without_llm():
    llm = FakeLLM(['{"intent":"refund"}'])
    state = new_state(scope=Scope.for_user(1), text="订单 #A1002 我要退款")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "refund" and out["order_no"] == "#A1002"


@pytest.mark.parametrize("bad", ['{"intent":"没这个意图"}', "纯文本"])
async def test_classify_falls_back_to_unknown(bad):
    llm = FakeLLM([bad, bad])
    state = new_state(scope=Scope.for_user(1), text="??")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "unknown"


async def test_classify_falls_back_to_keyword_rule_when_llm_dead():
    """LLM 完全不可用时，关键词兜底保证 demo 不翻车。"""
    llm = FakeLLM(["垃圾输出", "垃圾输出"])
    state = new_state(scope=Scope.for_user(1), text="我要退款")
    out = await classify_node(state, llm=llm)
    assert out["intent"] == "refund"
    assert out["degraded"] is True
```

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.agent.nodes.classify'`

**Step 3: 最小实现**

`state.py`：

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    actor_role: Literal["user", "merchant"]
    actor_id: int
    merchant_id: int | None
    intent: str
    order_no: str | None
    refund_amount: Decimal | None
    refund_draft: dict | None
    human_task_id: int | None
    human_decision: str | None
    human_note: str | None
    triggering_rule: str | None
    degraded: bool
    reply: str | None
    widgets: list[dict]


def new_state(*, scope: Scope, text: str) -> AgentState
```

`prompts/classify.py`：`SYSTEM` 常量 —— 封闭枚举说明 + 输出格式 `{"intent": "..."}` + 5 条 few-shot（含一条专治「订单到哪了」被误判成 `refund` 的反例）。

`nodes/classify.py`：

```python
INTENTS = ("product", "order", "refund", "chitchat", "unknown")

async def classify_node(state: AgentState, *, llm) -> dict
```

执行顺序：
1. 正则抽 `order_no` / `refund_amount`（不依赖模型）
2. `ask_json()` 拿 `intent`，校验在 `INTENTS` 内
3. 失败 → 关键词规则兜底，`degraded=True`
4. 命中 `refund` 但缺 `order_no` → 保持 `refund`，由 `refund_node` 追问

**Step 4: 确认通过**

```bash
uv run pytest tests/test_node_classify.py -v
```

Expected: PASS — `5 passed`

**Step 5: 提交** → `git commit -m "feat(agent): add state and classify node with rule fallback"`

---

### Task 17: product / order / chitchat 节点

**Files:**
- Create: `backend/app/agent/nodes/product.py`
- Create: `backend/app/agent/nodes/order.py`
- Create: `backend/app/agent/nodes/chitchat.py`
- Test: `backend/tests/test_nodes_read.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_nodes_read.py
from app.agent.nodes.order import order_node
from app.agent.nodes.product import product_node
from app.agent.scope import Scope
from app.agent.state import new_state
from tests.fakes import FakeLLM


async def test_product_node_returns_widget_and_reply(session, seeded):
    llm = FakeLLM(["为您找到以下商品"])
    state = new_state(scope=Scope.for_user(seeded.user_id), text="有耳机吗")
    state["intent"] = "product"
    out = await product_node(state, session=session, llm=llm)
    assert out["widgets"][0]["kind"] == "product_list"
    assert out["reply"]


async def test_order_node_missing_order_no_asks_back(session, seeded):
    llm = FakeLLM([])  # 不应被调用
    state = new_state(scope=Scope.for_user(seeded.user_id), text="订单到哪了")
    state["intent"] = "order"
    out = await order_node(state, session=session, llm=llm)
    assert "订单号" in out["reply"] and out["widgets"] == []
    assert llm.calls == 0


async def test_order_node_emits_order_widget(session, seeded):
    llm = FakeLLM(["您的订单已发货"])
    state = new_state(scope=Scope.for_user(seeded.user_id), text=f"{seeded.order_no} 到哪了")
    state["intent"] = "order"
    state["order_no"] = seeded.order_no
    out = await order_node(state, session=session, llm=llm)
    assert out["widgets"][0]["data"]["order_no"] == seeded.order_no


async def test_order_node_handles_not_found(session, seeded):
    llm = FakeLLM([])
    state = new_state(scope=Scope.for_user(seeded.user_id), text="x")
    state["intent"] = "order"
    state["order_no"] = "#A9999"
    out = await order_node(state, session=session, llm=llm)
    assert "没有找到" in out["reply"]
```

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.agent.nodes.product'`

**Step 3: 最小实现**

三个节点统一签名：`async def xxx_node(state, *, session, llm) -> dict`。

- 调工具取数据 → 组装 `widgets` → 调 LLM 把结构化数据转成一句自然语言
- 数据为空 / 缺槽位时**不调 LLM**，直接返回固定话术（省时且不出错）
- `chitchat_node` 不查库，直接用 LLM 生成一句简短回应

**Step 4: 确认通过**

```bash
uv run pytest tests/test_nodes_read.py -v
```

Expected: PASS — `4 passed`

**Step 5: 提交** → `git commit -m "feat(agent): add product, order, chitchat nodes"`

---

### Task 18: refund 节点与人工挂起

**Files:**
- Create: `backend/app/agent/nodes/refund.py`
- Create: `backend/app/agent/nodes/human.py`
- Test: `backend/tests/test_node_refund.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_node_refund.py
from decimal import Decimal

from sqlalchemy import select

from app.agent.nodes.human import human_review_node
from app.agent.nodes.refund import refund_node, finalize_refund_node
from app.agent.scope import Scope
from app.agent.state import new_state
from app.models import HumanTask, Refund, RefundStatus
from tests.fakes import FakeLLM


async def test_refund_node_missing_order_no_asks_back(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="我要退款")
    state["intent"] = "refund"
    out = await refund_node(state, session=session, llm=FakeLLM([]))
    assert "订单号" in out["reply"]


async def test_refund_node_auto_path_sets_no_trigger(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="不想要了")
    state.update(intent="refund", order_no=seeded.paid_order_no, refund_amount=Decimal("50.00"))
    out = await refund_node(state, session=session, llm=FakeLLM([]))
    assert out["triggering_rule"] is None
    assert out["refund_draft"]["status"] == RefundStatus.DRAFT.value


async def test_refund_node_human_path_sets_trigger(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", order_no=seeded.shipped_order_no, refund_amount=Decimal("599.00"))
    out = await refund_node(state, session=session, llm=FakeLLM([]))
    assert out["triggering_rule"] == "already_shipped"


async def test_human_review_node_creates_task_and_interrupts(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", order_no=seeded.shipped_order_no,
                 refund_amount=Decimal("599.00"), refund_draft={"id": 1, "amount": "599.00"},
                 triggering_rule="already_shipped")
    out = await human_review_node(state, session=session, thread_id="conv-1")
    task = (await session.execute(select(HumanTask).where(HumanTask.thread_id == "conv-1"))).scalar_one()
    assert task.merchant_id == seeded.merchant_id
    assert task.status.value == "pending"
    assert out["__interrupt__"][0].value["task_id"] == task.id


async def test_human_review_node_is_idempotent_per_thread(session, seeded):
    """重复进入不能建出两条待办（防 checkpoint 重放）。"""
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", order_no=seeded.shipped_order_no,
                 refund_amount=Decimal("599.00"), triggering_rule="already_shipped")
    await human_review_node(state, session=session, thread_id="conv-1")
    await human_review_node(state, session=session, thread_id="conv-1")
    tasks = (await session.execute(select(HumanTask).where(HumanTask.thread_id == "conv-1"))).scalars().all()
    assert len(tasks) == 1


async def test_finalize_refund_approved_marks_refunded(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", refund_draft={"id": seeded.draft_refund_id},
                 human_decision="approved")
    await finalize_refund_node(state, session=session)
    row = (await session.execute(select(Refund).where(Refund.id == seeded.draft_refund_id))).scalar_one()
    assert row.status is RefundStatus.REFUNDED


async def test_finalize_refund_rejected_records_note(session, seeded):
    state = new_state(scope=Scope.for_user(seeded.user_id), text="退款")
    state.update(intent="refund", refund_draft={"id": seeded.draft_refund_id},
                 human_decision="rejected", human_note="超期")
    await finalize_refund_node(state, session=session)
    row = (await session.execute(select(Refund).where(Refund.id == seeded.draft_refund_id))).scalar_one()
    assert row.status is RefundStatus.REJECTED and row.review_note == "超期"
```

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.agent.nodes.refund'`

**Step 3: 最小实现**

`refund_node`：
1. 无 `order_no` → 追问并结束本轮
2. 无 `refund_amount` → 默认取 `order.total_amount`（全额退）
3. `check_refund_policy` → `eligible=False` 直接告知原因
4. `create_refund_draft` → 写 `status=DRAFT`，落 `refund_draft`
5. 把 `trigger` 写入 `triggering_rule`

`human_review_node`：
1. 以 `thread_id` 查已有 `HumanTask`，存在则直接复用（幂等）
2. 不存在则建 `HumanTask`，`payload` 快照订单号、金额、原因、触发规则
3. `refunds.status` 置 `PENDING`
4. 调 `interrupt({"task_id": ..., "kind": "refund_review"})`

`finalize_refund_node`：读 `human_decision` → `approved` 调 `submit_refund(decision="approved")` 置 `REFUNDED`；`rejected` 置 `REJECTED` 并写 note；随后把 `HumanTask.status` 同步为终态。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_node_refund.py -v
```

Expected: PASS — `7 passed`

**Step 5: 提交** → `git commit -m "feat(agent): add refund node, human review interrupt and finalize"`

---

### Task 19: respond 节点与图组装

**Files:**
- Create: `backend/app/agent/nodes/respond.py`
- Create: `backend/app/agent/graph.py`
- Test: `backend/tests/test_graph.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_graph.py
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agent.graph import build_graph
from app.agent.scope import Scope
from tests.fakes import FakeLLM


async def test_graph_routes_product_intent(session, seeded, checkpointer):
    graph = build_graph(session=session, llm=FakeLLM(['{"intent":"product"}', "为您找到以下商品"]),
                        checkpointer=checkpointer)
    out = await graph.ainvoke(
        {"text": "有耳机吗", "actor_role": "user", "actor_id": seeded.user_id, "merchant_id": None},
        config={"configurable": {"thread_id": "t-product"}},
    )
    assert out["intent"] == "product"
    assert out["reply"]


async def test_graph_unknown_intent_does_not_crash(session, seeded, checkpointer):
    graph = build_graph(session=session, llm=FakeLLM(["垃圾", "垃圾"]), checkpointer=checkpointer)
    out = await graph.ainvoke(
        {"text": "???", "actor_role": "user", "actor_id": seeded.user_id, "merchant_id": None},
        config={"configurable": {"thread_id": "t-unknown"}},
    )
    assert out["intent"] == "unknown" and out["reply"]


async def test_graph_auto_approves_small_refund(session, seeded, checkpointer):
    llm = FakeLLM(['{"intent":"refund"}', "退款已提交"])
    graph = build_graph(session=session, llm=llm, checkpointer=checkpointer)
    out = await graph.ainvoke(
        {"text": f"{seeded.paid_order_no} 退 50 元", "actor_role": "user",
         "actor_id": seeded.user_id, "merchant_id": None},
        config={"configurable": {"thread_id": "t-auto"}},
    )
    assert out["triggering_rule"] is None
    assert out["human_task_id"] is None
    assert out["refund_state"] == "refunded"


async def test_graph_interrupts_then_resumes(session, seeded, checkpointer):
    llm = FakeLLM(['{"intent":"refund"}', "已提交商家审核", "退款已受理"])
    graph = build_graph(session=session, llm=llm, checkpointer=checkpointer)
    cfg = {"configurable": {"thread_id": "t-hitl"}}

    first = await graph.ainvoke(
        {"text": f"{seeded.shipped_order_no} 我要退款", "actor_role": "user",
         "actor_id": seeded.user_id, "merchant_id": None}, config=cfg)
    assert "__interrupt__" in first
    task_id = first["__interrupt__"][0].value["task_id"]

    second = await graph.ainvoke(Command(resume={"decision": "approved", "note": None}), config=cfg)
    assert second["human_task_id"] == task_id
    assert second["refund_state"] == "refunded"
    assert second["reply"]


async def test_graph_resume_with_missing_thread_raises(session, seeded, checkpointer):
    graph = build_graph(session=session, llm=FakeLLM([]), checkpointer=checkpointer)
    import pytest
    with pytest.raises(Exception):
        await graph.ainvoke(Command(resume={"decision": "approved"}),
                            config={"configurable": {"thread_id": "never-started"}})
```

`conftest.py` 新增 `checkpointer` fixture：`MemorySaver()`（单测不依赖 PG），端到端测试另用 PG checkpointer。

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.agent.graph'`

**Step 3: 最小实现**

`nodes/respond.py`：把该轮 `reply` 与 `widgets` 落 `messages` 表，并把 `refund_state` 归一化为对外可读值（`refunded` / `rejected` / `draft`）。

`graph.py`：

```python
def build_graph(*, session, llm, checkpointer) -> CompiledStateGraph
```

节点装配：用 `functools.partial` 把 `session` / `llm` 注入每个节点（demo 规模下最直接，避免全局状态）。

条件边：

```python
def route_after_refund(state) -> str:
    return "respond" if state.get("human_task_id") is None and state.get("triggering_rule") is None else "human_review"

def route_after_finalize(state) -> str:
    return "respond"
```

图结构：

```
START → classify → (product|order|refund|chitchat|unknown)
  product  → product_node  → respond → END
  order    → order_node    → respond → END
  chitchat → chitchat_node → respond → END
  unknown  → respond → END
  refund   → refund_node → [无触发] respond → END
                         → [有触发] human_review → finalize_refund → respond → END
```

> `refund_node` 走追问路径（缺订单号）时也不得进 `human_review` —— 在 `route_after_refund` 里以 `refund_draft is None` 一并拦掉。

**Step 4: 确认通过**

```bash
uv run pytest tests/test_graph.py -v
```

Expected: PASS — `6 passed`

**Step 5: 提交** → `git commit -m "feat(agent): assemble langgraph with human-in-the-loop"`

---

## Phase 4 · API 层

### Task 20: 身份依赖 `get_current_actor`

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Test: `backend/tests/test_deps.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_deps.py
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
```

**Step 2: 确认失败** → FAIL — `ModuleNotFoundError: No module named 'app.api.deps'`

**Step 3: 最小实现**

```python
@dataclass(frozen=True, slots=True)
class Actor:
    id: int
    role: Literal["user", "merchant"]
    merchant_id: int | None
    def to_scope(self) -> Scope: ...


async def resolve_actor(session: AsyncSession, *, x_actor_id: int) -> Actor
async def get_current_actor(
    session: AsyncSession = Depends(get_session),
    x_actor_id: int = Header(..., alias="X-Actor-Id"),
) -> Actor
```

查不到抛 `HTTPException(401, detail="actor_not_found")`。响应头 `X-Merchant-Id` 由前端展示，不在后端校验。

**Step 4: 确认通过** → PASS — `4 passed`
**Step 5: 提交** → `git commit -m "feat(api): add demo actor dependency"`

---

### Task 21: SSE 对话流接口

**Files:**
- Create: `backend/app/api/chat.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_chat.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_api_chat.py
import json

from httpx import ASGITransport, AsyncClient

from app.main import app


def parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.strip().split("\n\n"):
        if block.startswith("data:"):
            events.append(json.loads(block[len("data:"):].strip()))
    return events


async def test_chat_stream_emits_done(client, seeded, override_llm):
    resp = await client.post("/api/chat/stream",
                             json={"message": "有耳机吗"},
                             headers={"X-Actor-Id": str(seeded.user_id)})
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "widget" for e in events)


async def test_chat_stream_requires_actor(client):
    resp = await client.post("/api/chat/stream", json={"message": "hi"})
    assert resp.status_code == 422  # 缺 header


async def test_chat_stream_emits_awaiting_human(client, seeded, override_llm):
    resp = await client.post("/api/chat/stream",
                             json={"message": f"{seeded.shipped_order_no} 我要退款"},
                             headers={"X-Actor-Id": str(seeded.user_id)})
    events = parse_sse(resp.text)
    assert any(e["type"] == "awaiting_human" for e in events)


async def test_chat_stream_unknown_actor_401(client):
    resp = await client.post("/api/chat/stream", json={"message": "hi"},
                             headers={"X-Actor-Id": "999999"})
    assert resp.status_code == 401
```

`conftest.py` 新增：`client` fixture（`ASGITransport` + `app.dependency_overrides` 注入测试 session）、`override_llm` fixture（把 `get_llm` 换成 `FakeLLM`）。

**Step 2: 确认失败**

```bash
uv add sse-starlette
uv run pytest tests/test_api_chat.py -v
```

Expected: FAIL — `404 Not Found` for `/api/chat/stream`

**Step 3: 最小实现**

```python
@router.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, actor=Depends(get_current_actor), session=Depends(get_session))
```

- 首次请求若无 `conversation_id`，建 `conversation` 并落用户消息
- 用 `graph.astream(..., stream_mode="custom")` 配合节点内 `get_stream_writer()` 推送事件
- `conversation_id` 作为 `thread_id`
- 事件类型：`token` / `tool_call` / `widget` / `awaiting_human` / `done` / `error`
- 图抛 `GraphInterrupt` 时**不要**当异常吞掉：捕获后读 `__interrupt__` 的 `task_id`，推 `awaiting_human` 再推 `done`

`main.py` 加 `lifespan`：启动时建 `AsyncPostgresSaver` 并 `setup()`，挂到 `app.state.checkpointer`。

**Step 4: 确认通过** → PASS — `4 passed`
**Step 5: 提交** → `git commit -m "feat(api): add sse chat stream with human handoff events"`

---

### Task 22: 会话历史与轮询状态接口

**Files:**
- Modify: `backend/app/api/chat.py`
- Test: `backend/tests/test_api_conversations.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_api_conversations.py
async def test_get_conversation_returns_messages(client, seeded, override_llm):
    r = await client.post("/api/chat/stream", json={"message": "有耳机吗"},
                          headers={"X-Actor-Id": str(seeded.user_id)})
    conv_id = r.headers["X-Conversation-Id"]
    resp = await client.get(f"/api/conversations/{conv_id}",
                            headers={"X-Actor-Id": str(seeded.user_id)})
    body = resp.json()
    assert body["id"] == int(conv_id)
    assert any(m["role"] == "user" for m in body["messages"])
    assert any(m["role"] == "assistant" for m in body["messages"])


async def test_status_pending_true_after_handoff(client, seeded, override_llm):
    r = await client.post("/api/chat/stream",
                          json={"message": f"{seeded.shipped_order_no} 我要退款"},
                          headers={"X-Actor-Id": str(seeded.user_id)})
    conv_id = r.headers["X-Conversation-Id"]
    body = (await client.get(f"/api/conversations/{conv_id}/status",
                             headers={"X-Actor-Id": str(seeded.user_id)})).json()
    assert body == {"pending_human": True, "task_id": body["task_id"]}
    assert body["task_id"] is not None


async def test_status_pending_false_after_resolve(client, seeded, override_llm):
    ...  # 走完审批后再查，断言 pending_human is False


async def test_customer_cannot_read_others_conversation(client, seeded, other_customer):
    resp = await client.get("/api/conversations/1",
                            headers={"X-Actor-Id": str(other_customer.id)})
    assert resp.status_code == 404
```

**Step 2: 确认失败** → FAIL — `404`

**Step 3: 最小实现**

- `GET /api/conversations/{id}`：校验 `conversation.user_id == actor.id`，否则 404；返回消息列表含 `widgets`
- `GET /api/conversations/{id}/status`：按 `thread_id` 查 `HumanTask`，返回 `{"pending_human": bool, "task_id": int | None, "decision": str | None}`
- SSE 响应头带 `X-Conversation-Id`，供前端保存

**Step 4: 确认通过** → PASS — `4 passed`
**Step 5: 提交** → `git commit -m "feat(api): add conversation history and status polling"`

---

### Task 23: 商家审批接口

**Files:**
- Create: `backend/app/api/merchant.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_merchant.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_api_merchant.py
from sqlalchemy import select
from app.models import Refund, RefundStatus


async def test_list_pending_tasks_scoped_to_tenant(client, seeded, interrupted_task):
    a = await client.get("/api/merchant/tasks?status=pending",
                         headers={"X-Actor-Id": str(seeded.merchant_user_id)})
    b = await client.get("/api/merchant/tasks?status=pending",
                         headers={"X-Actor-Id": str(seeded.other_merchant_user_id)})
    assert [t["id"] for t in a.json()] == [interrupted_task.id]
    assert b.json() == []


async def test_customer_cannot_access_merchant_api(client, seeded):
    resp = await client.get("/api/merchant/tasks", headers={"X-Actor-Id": str(seeded.user_id)})
    assert resp.status_code == 403


async def test_resolve_approves_and_resumes_graph(client, session, seeded, interrupted_task):
    resp = await client.post(f"/api/merchant/tasks/{interrupted_task.id}/resolve",
                             json={"decision": "approved", "note": "已核对"},
                             headers={"X-Actor-Id": str(seeded.merchant_user_id)})
    assert resp.status_code == 200
    assert resp.json()["refund_state"] == "refunded"
    row = (await session.execute(select(Refund).where(Refund.order_id == interrupted_task_order_id))).scalar_one()
    assert row.status is RefundStatus.REFUNDED


async def test_resolve_cross_tenant_returns_404(client, seeded, interrupted_task):
    resp = await client.post(f"/api/merchant/tasks/{interrupted_task.id}/resolve",
                             json={"decision": "approved"},
                             headers={"X-Actor-Id": str(seeded.other_merchant_user_id)})
    assert resp.status_code == 404


async def test_resolve_twice_returns_409(client, seeded, interrupted_task):
    h = {"X-Actor-Id": str(seeded.merchant_user_id)}
    body = {"decision": "approved"}
    await client.post(f"/api/merchant/tasks/{interrupted_task.id}/resolve", json=body, headers=h)
    again = await client.post(f"/api/merchant/tasks/{interrupted_task.id}/resolve", json=body, headers=h)
    assert again.status_code == 409
```

**Step 2: 确认失败** → FAIL — `404`

**Step 3: 最小实现**

```python
@router.get("/api/merchant/tasks")
@router.post("/api/merchant/tasks/{task_id}/resolve")
```

`resolve` 流程：
1. 校验 `actor.role == "merchant"`，否则 403
2. 按 `id` + `merchant_id` 双条件查 `HumanTask`，查不到 404（**不能只按 id 查后再比较**，否则会泄露存在性）
3. `status != pending` → 409
4. 更新 `HumanTask.status` / `assignee_id` / `resolved_at`
5. `graph.ainvoke(Command(resume={"decision": ..., "note": ...}), config={"configurable": {"thread_id": task.thread_id}})`
6. 返回 `{"refund_state": ...}` 供商家端即时反馈

**Step 4: 确认通过** → PASS — `5 passed`
**Step 5: 提交** → `git commit -m "feat(api): add merchant approval endpoints"`

---

## Phase 5 · 前端

### Task 24: Vite 脚手架、Tailwind 与角色守卫

**Files:**
- Create: `frontend/package.json`、`frontend/vite.config.ts`、`frontend/index.html`
- Create: `frontend/src/main.tsx`、`frontend/src/App.tsx`、`frontend/src/router.tsx`
- Create: `frontend/src/index.css`
- Test: `frontend/src/router.test.tsx`

**Step 1: 写失败的测试**

```tsx
// frontend/src/router.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from './router'

describe('role guard', () => {
  it('redirects guest to role picker', () => {
    render(<MemoryRouter initialEntries={['/chat']}><AppRoutes actor={null} /></MemoryRouter>)
    expect(screen.getByText(/选择身份/)).toBeInTheDocument()
  })

  it('blocks customer from merchant page', () => {
    const actor = { id: 1, role: 'user' as const, name: '演示用户', merchantId: null }
    render(<MemoryRouter initialEntries={['/merchant']}><AppRoutes actor={actor} /></MemoryRouter>)
    expect(screen.getByText(/无权访问/)).toBeInTheDocument()
  })

  it('allows merchant into merchant page', () => {
    const actor = { id: 2, role: 'merchant' as const, name: '青柠数码', merchantId: 1 }
    render(<MemoryRouter initialEntries={['/merchant']}><AppRoutes actor={actor} /></MemoryRouter>)
    expect(screen.getByText(/待审批/)).toBeInTheDocument()
  })
})
```

**Step 2: 确认失败**

```bash
cd /Users/kk/code/project/smart_service/frontend
npm create vite@latest . -- --template react-ts
npm i -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom
npm i react-router-dom
npm test -- --run
```

Expected: FAIL — 找不到 `./router`

**Step 3: 最小实现**

- `vite.config.ts`：`plugins: [react(), tailwindcss()]`，`server.proxy['/api'] = 'http://127.0.0.1:8000'`，`test: { environment: 'jsdom', setupFiles: ['./src/setupTests.ts'] }`
- `src/index.css`：`@import "tailwindcss";`
- `router.tsx`：导出 `AppRoutes({ actor })`，`/` → `RolePickPage`，`/chat` → `ChatPage`，`/merchant` → `MerchantPage`；守卫逻辑：`actor === null` 跳身份选择，角色不匹配渲染「无权访问」

**Step 4: 确认通过** → `npm test -- --run` → PASS — `3 passed`
**Step 5: 提交** → `git commit -m "feat(frontend): scaffold vite app with role guard"`

---

### Task 25: 身份与 API 客户端

**Files:**
- Create: `frontend/src/lib/actor.ts`、`frontend/src/lib/api.ts`、`frontend/src/types.ts`
- Test: `frontend/src/lib/actor.test.ts`

**Step 1: 写失败的测试**

```ts
// frontend/src/lib/actor.test.ts
import { beforeEach, describe, expect, it } from 'vitest'
import { loadActor, saveActor, clearActor, DEMO_ACTORS } from './actor'

beforeEach(() => { localStorage.clear(); clearActor() })

describe('actor store', () => {
  it('exposes exactly two demo identities: one customer, two merchants', () => {
    expect(DEMO_ACTORS.filter(a => a.role === 'user')).toHaveLength(1)
    expect(DEMO_ACTORS.filter(a => a.role === 'merchant')).toHaveLength(2)
  })

  it('returns null when nothing stored', () => {
    expect(loadActor()).toBeNull()
  })

  it('round-trips the selected actor', () => {
    saveActor(DEMO_ACTORS[1])
    expect(loadActor()).toEqual(DEMO_ACTORS[1])
  })

  it('discards corrupted storage', () => {
    localStorage.setItem('smart-service.actor', '{not json')
    expect(loadActor()).toBeNull()
  })

  it('discards unknown actor ids', () => {
    localStorage.setItem('smart-service.actor', JSON.stringify({ id: 999, role: 'user' }))
    expect(loadActor()).toBeNull()
  })
})
```

**Step 2: 确认失败** → FAIL — 找不到 `./actor`

**Step 3: 最小实现**

- `types.ts`：`Actor`、`ChatEvent` 联合类型（对应 SSE 六种事件）、`Widget`、`Message`
- `actor.ts`：`DEMO_ACTORS` 常量（与后端 seed 的 id 对齐）、`loadActor` / `saveActor` / `clearActor`
- `api.ts`：`request<T>(path, init)` 自动注入 `X-Actor-Id`，非 2xx 抛带 `status` 的 `ApiError`

**Step 4: 确认通过** → PASS — `5 passed`
**Step 5: 提交** → `git commit -m "feat(frontend): add actor store and api client"`

---

### Task 26: SSE 解析与 useChatStream

**Files:**
- Create: `frontend/src/lib/sse.ts`、`frontend/src/hooks/useChatStream.ts`
- Test: `frontend/src/lib/sse.test.ts`

**Step 1: 写失败的测试**

```ts
// frontend/src/lib/sse.test.ts
import { describe, expect, it } from 'vitest'
import { parseSSEChunk } from './sse'

describe('parseSSEChunk', () => {
  it('parses a single complete event', () => {
    expect(parseSSEChunk('data: {"type":"token","text":"你好"}\n\n').events)
      .toEqual([{ type: 'token', text: '你好' }])
  })

  it('keeps the trailing partial block as buffer', () => {
    const r = parseSSEChunk('data: {"type":"token","text":"a"}\n\ndata: {"type":"tok')
    expect(r.events).toHaveLength(1)
    expect(r.buffer).toBe('data: {"type":"tok')
  })

  it('resumes correctly from a carried buffer', () => {
    const r = parseSSEChunk('en","text":"b"}\n\n', 'data: {"type":"tok')
    expect(r.events).toEqual([{ type: 'token', text: 'b' }])
    expect(r.buffer).toBe('')
  })

  it('ignores malformed json blocks', () => {
    expect(parseSSEChunk('data: {broken\n\n').events).toEqual([])
  })

  it('ignores ping comments', () => {
    expect(parseSSEChunk(': ping\n\n').events).toEqual([])
  })
})
```

**Step 2: 确认失败** → FAIL — 找不到 `./sse`

**Step 3: 最小实现**

- `sse.ts`：`parseSSEChunk(chunk: string, buffer = '') => { events: ChatEvent[]; buffer: string }` —— **保留未闭合块**，这是分片解析最容易出 bug 的地方
- `useChatStream.ts`：`send(text)` → `fetch` POST + `ReadableStream` reader → 逐块 `parseSSEChunk` → 累积 `messages` / `streamingText` / `widgets`；收到 `awaiting_human` 置 `pendingTaskId` 并停止流

**Step 4: 确认通过** → PASS — `5 passed`
**Step 5: 提交** → `git commit -m "feat(frontend): add sse parser and chat stream hook"`

---

### Task 27: 对话组件

**Files:**
- Create: `frontend/src/components/MessageList.tsx`、`MessageBubble.tsx`、`ToolCallTrace.tsx`
- Test: `frontend/src/components/MessageBubble.test.tsx`

**Step 1: 写失败的测试**

```tsx
// frontend/src/components/MessageBubble.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MessageBubble } from './MessageBubble'

describe('MessageBubble', () => {
  it('renders user text', () => {
    render(<MessageBubble role="user" content="有耳机吗" widgets={[]} toolCalls={[]} />)
    expect(screen.getByText('有耳机吗')).toBeInTheDocument()
  })

  it('renders tool call trace for assistant turn', () => {
    render(<MessageBubble role="assistant" content="已查到" widgets={[]}
      toolCalls={[{ name: 'search_products', args: { keyword: '耳机' } }]} />)
    expect(screen.getByText('search_products')).toBeInTheDocument()
  })

  it('renders empty content while streaming without crash', () => {
    render(<MessageBubble role="assistant" content="" widgets={[]} toolCalls={[]} streaming />)
    expect(document.querySelector('.animate-pulse')).toBeTruthy()
  })
})
```

**Step 2: 确认失败** → FAIL — 找不到 `./MessageBubble`

**Step 3: 最小实现**

- `MessageBubble`：按 `role` 区分左右布局；`toolCalls` 非空时渲染 `ToolCallTrace`（可折叠，展示工具名与参数）；`streaming && !content` 显示光标动画
- `ToolCallTrace`：琥珀色标签 + JSON 参数
- `MessageList`：滚动容器，新消息自动滚到底

**Step 4: 确认通过** → PASS — `3 passed`
**Step 5: 提交** → `git commit -m "feat(frontend): add message list and tool call trace"`

---

### Task 28: 业务卡片与挂起态轮询

**Files:**
- Create: `frontend/src/components/OrderCard.tsx`、`RefundCard.tsx`、`StatusBadge.tsx`、`ProductList.tsx`
- Create: `frontend/src/hooks/usePolling.ts`
- Test: `frontend/src/components/OrderCard.test.tsx`、`frontend/src/hooks/usePolling.test.ts`

**Step 1: 写失败的测试**

```tsx
// frontend/src/components/OrderCard.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OrderCard } from './OrderCard'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('shows pending human review in amber', () => {
    render(<StatusBadge status="pending" label="待审核" />)
    expect(screen.getByText('待审核')).toBeInTheDocument()
  })
})

describe('OrderCard', () => {
  it('renders order no, status and amount', () => {
    render(<OrderCard data={{
      order_no: '#A1002', status: 'shipped', total_amount: '599.00',
      created_at: '2026-09-01', items: [{ name: '降噪耳机', quantity: 1, unit_price: '599.00' }],
    }} />)
    expect(screen.getByText('#A1002')).toBeInTheDocument()
    expect(screen.getByText('已发货')).toBeInTheDocument()
    expect(screen.getByText(/599\.00/)).toBeInTheDocument()
  })
})
```

```ts
// frontend/src/hooks/usePolling.test.ts
import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePolling } from './usePolling'

describe('usePolling', () => {
  it('does not poll when disabled', () => {
    const fn = vi.fn()
    renderHook(() => usePolling(fn, 50, false))
    vi.advanceTimersByTime?.(200)
    expect(fn).not.toHaveBeenCalled()
  })

  it('stops polling once predicate returns true', async () => {
    const fn = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(false).mockResolvedValue(true)
    renderHook(() => usePolling(fn, 10, true))
    await waitFor(() => expect(fn.mock.calls.length).toBeGreaterThanOrEqual(2))
    const count = fn.mock.calls.length
    await new Promise(r => setTimeout(r, 50))
    expect(fn.mock.calls.length).toBe(count)
  })
})
```

**Step 2: 确认失败** → FAIL — 找不到 `./OrderCard`

**Step 3: 最小实现**

- `OrderCard`：订单号 / 状态徽章 / 金额（`¥` 前缀）/ 商品行 / 时间
- `RefundCard`：退款单号 / 金额 / 状态机进度（`draft → pending → approved/rejected → refunded` 四段点线，当前段高亮）
- `StatusBadge`：状态 → 文案 + 颜色的映射表，集中在组件内
- `ProductList`：商品卡网格（名称 / 价格 / 库存）
- `usePolling(fn, intervalMs, enabled)`：`enabled` 为真时按间隔调用 `fn`，`fn` 返回 `true` 表示达成条件并自动停止

> CLAUDE 约定：订单状态用中性灰蓝，退款审批通过用绿色、驳回用红色、待审核用琥珀色。

**Step 4: 确认通过** → PASS
**Step 5: 提交** → `git commit -m "feat(frontend): add business cards and polling hook"`

---

### Task 29: 对话页

**Files:**
- Create: `frontend/src/pages/ChatPage.tsx`、`frontend/src/pages/RolePickPage.tsx`
- Modify: `frontend/src/router.tsx`
- Test: `frontend/src/pages/ChatPage.test.tsx`

**Step 1: 写失败的测试**

```tsx
// frontend/src/pages/ChatPage.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatPage } from './ChatPage'

vi.mock('../hooks/useChatStream', () => ({
  useChatStream: () => ({
    messages: [{ id: '1', role: 'user', content: '有耳机吗', widgets: [], toolCalls: [] }],
    send: vi.fn(), streaming: false, pendingTaskId: null,
  }),
}))

describe('ChatPage', () => {
  it('renders identity bar and existing messages', () => {
    render(<ChatPage actor={{ id: 1, role: 'user', name: '演示用户', merchantId: null }} />)
    expect(screen.getByText('演示用户')).toBeInTheDocument()
    expect(screen.getByText('有耳机吗')).toBeInTheDocument()
  })

  it('shows handoff banner when a human task is pending', () => {
    ... // pendingTaskId = 7 时渲染「已转人工，等待商家审核」
  })

  it('renders quick demo prompts', () => {
    render(<ChatPage actor={{ id: 1, role: 'user', name: '演示用户', merchantId: null }} />)
    expect(screen.getByRole('button', { name: /有蓝牙耳机吗/ })).toBeInTheDocument()
  })
})
```

**Step 2: 确认失败** → FAIL — 找不到 `./ChatPage`

**Step 3: 最小实现**

`ChatPage`：
- 顶部身份条（当前身份 + 切换按钮）
- `MessageList` + 输入框（Enter 发送，Shift+Enter 换行）
- 三个演示快捷问题按钮，一键发包
- `pendingTaskId` 非空时：渲染「已转人工」横幅 + 启动 `usePolling` 轮询 `/api/conversations/{id}/status`，`pending_human` 转 false 后拉一次历史并关闭横幅

`RolePickPage`：列出 `DEMO_ACTORS`，点击选中并跳转到对应路由。

**Step 4: 确认通过** → PASS
**Step 5: 提交** → `git commit -m "feat(frontend): add chat page and role picker"`

---

### Task 30: 商家审批台

**Files:**
- Create: `frontend/src/pages/MerchantPage.tsx`
- Test: `frontend/src/pages/MerchantPage.test.tsx`

**Step 1: 写失败的测试**

```tsx
// frontend/src/pages/MerchantPage.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MerchantPage } from './MerchantPage'

const actor = { id: 2, role: 'merchant' as const, name: '青柠数码', merchantId: 1 }

describe('MerchantPage', () => {
  it('lists pending refund tasks of own tenant', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify([
      { id: 7, payload: { order_no: '#A1002', amount: '599.00', trigger: 'already_shipped' },
        created_at: '2026-09-17T10:00:00Z', status: 'pending' },
    ]), { status: 200 }))
    render(<MerchantPage actor={actor} />)
    expect(await screen.findByText('#A1002')).toBeInTheDocument()
    expect(screen.getByText(/已发货/)).toBeInTheDocument()   // 触发原因中文映射
  })

  it('shows empty state when no pending task', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response('[]', { status: 200 }))
    render(<MerchantPage actor={actor} />)
    expect(await screen.findByText(/暂无待审批/)).toBeInTheDocument()
  })

  it('posts resolve and refreshes list', async () => { ... })
})
```

**Step 2: 确认失败** → FAIL — 找不到 `./MerchantPage`

**Step 3: 最小实现**

`MerchantPage`：
- 顶部身份条，明确显示「青柠数码 · 租户 #1」，让隔离效果可被看见
- 待审批工单列表：订单号、退款金额、申请原因、**触发转人工的规则**（中文映射）、申请时间
- 每行「批准」/「驳回」按钮；驳回弹原因输入框
- 提交后 `POST /api/merchant/tasks/{id}/resolve`，成功后从列表移除并 toast 提示
- 空态文案：「暂无待审批工单」

**Step 4: 确认通过** → PASS
**Step 5: 提交** → `git commit -m "feat(frontend): add merchant approval console"`

---

## Phase 6 · 串通

### Task 31: 端到端演示测试

**Files:**
- Create: `backend/tests/test_e2e_demo.py`
- Modify: `backend/tests/conftest.py`

**Step 1: 写失败的测试**

```python
# backend/tests/test_e2e_demo.py
"""按 demo 五幕顺序跑完整链路，用真实 PG checkpointer（不是 MemorySaver）。"""


async def test_act1_ask_for_product(client, seeded, override_llm):
    ...

async def test_act2_query_order_status(client, seeded, override_llm):
    ...

async def test_act3_refund_triggers_handoff(client, seeded, override_llm):
    ...

async def test_act4_merchant_a_sees_task_merchant_b_does_not(client, seeded, override_llm):
    """租户隔离：商家 A 的待办列表里有，商家 B 的列表里没有。"""

async def test_act5_user_polls_and_receives_result(client, seeded, override_llm):
    """完整闭环：申请 → 挂起 → 审批 → 轮询拿到 refunded。"""
```

**Step 2: 确认失败** → FAIL — 测试函数体未实现（`assert False` 占位）

**Step 3: 实现**

- `conftest.py` 增加 session 级的 PG checkpointer fixture，并在用例间清理 `thread_id` 对应的 checkpoint
- 逐幕实现断言，第 4 幕必须同时断言 A 有、B 无
- 第 5 幕收尾断言 `refunds.status == refunded` 且 `conversation/status` 的 `pending_human is False`

**Step 4: 确认通过**

```bash
cd backend && uv run pytest -v
```

Expected: PASS — 全部用例通过（含前序所有测试）

**Step 5: 提交** → `git commit -m "test: add end-to-end demo scenario coverage"`

---

### Task 32: 启动脚本与 README

**Files:**
- Create: `Makefile`
- Create: `README.md`（仓库根目录，简短）
- Create: `doc/RUNBOOK.md`
- Modify: `doc/ARCHITECTURE.md`（补一节「已实现范围与偏差」）

**Step 1: 写失败的测试**

```python
# backend/tests/test_tooling.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_makefile_has_required_targets():
    text = (ROOT / "Makefile").read_text()
    for target in ("db-up", "migrate", "seed", "api", "web", "test"):
        assert f"{target}:" in text


def test_runbook_documents_omlx_startup():
    text = (ROOT / "doc" / "RUNBOOK.md").read_text()
    assert "mlx_lm.server" in text
```

**Step 2: 确认失败** → FAIL — `FileNotFoundError: Makefile`

**Step 3: 实现**

Makefile 目标：

| target | 命令 |
|---|---|
| `db-up` | `docker compose up -d db` |
| `db-down` | `docker compose down` |
| `migrate` | `cd backend && uv run alembic upgrade head` |
| `seed` | `cd backend && uv run python -m scripts.seed` |
| `api` | `cd backend && uv run uvicorn app.main:app --reload --port 8000` |
| `web` | `cd frontend && npm run dev` |
| `test` | `cd backend && uv run pytest` + `cd frontend && npm test -- --run` |

`doc/RUNBOOK.md`：写清 oMLX 启动方式（`mlx_lm.server --model <path> --port 8080`）、依赖顺序（db → migrate → seed → api → web）、两个演示身份的登录方式与 5 幕演示操作步骤。

**Step 4: 确认通过**

```bash
cd backend && uv run pytest tests/test_tooling.py -v
```

Expected: PASS — `2 passed`

**Step 5: 提交** → `git commit -m "docs: add makefile, runbook and readme"`

---

## 风险与待验证项

| 项 | 何时验证 | 不通过怎么办 |
|---|---|---|
| oMLX 实际响应格式与 OpenAI 兼容度 | Task 15 前先手动 `curl` 一次 `/v1/chat/completions` | 差异化部分封装进 `OMLXClient`，不改动上层 |
| `gemma-4-e2b-it-4bit` 意图分类准确率 | Task 16 完成后跑 20 条真实语句 | 扩 few-shot；仍不行则提高关键词规则兜底权重 |
| LangGraph `interrupt()` 在 `AsyncPostgresSaver` 下的重放行为 | Task 18 的幂等测试 | 幂等逻辑已在节点内，必要时改由 `human_tasks` 唯一索引兜底 |
| Tailwind v4 与 Vite 插件版本兼容 | Task 24 | 回退 Tailwind v3 + postcss |
| SSE 分片边界 | Task 26 的单测已覆盖 | buffer 保留逻辑已实现，补充更多边界用例 |

---

## 执行交接

计划已保存到 `doc/plans/2026-09-17-smart-service-implementation.md`。两种执行方式：

1. **Subagent-Driven** — 每个 Task 派一个全新子 agent 实现，任务之间插入规格审查与代码质量审查两轮检查
2. **Manual** — 你自己按 Task 顺序执行

选哪种？
