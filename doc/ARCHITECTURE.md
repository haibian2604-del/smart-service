# 智能客服 Agent 系统 — 架构设计

> 定位：演示型项目，重点展示 Agent 能力 —— 意图路由、工具调用、人工介入与中断恢复。
> 状态：设计已确认，待实施。

---

## 1. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + uv + LangGraph + SQLAlchemy + Alembic |
| 前端 | Vite + React + TypeScript + Tailwind CSS |
| 数据库 | PostgreSQL 16（业务表 + LangGraph checkpoint 同库） |
| LLM | 本地 oMLX，模型 `gemma-4-e2b-it-4bit`，OpenAI 兼容接口 `/v1` |
| 通信 | 对话走 SSE 流式；人工介入挂起期前端轮询会话状态 |

---

## 2. 系统分层

```
前端 · Vite + React + TS + Tailwind
  ├─ 对话工作台 /chat
  └─ 商家工作台 /merchant
        ↓ HTTP / SSE
后端 · FastAPI + uv
  ├─ SSE 对话流    POST /api/chat/stream
  ├─ 业务 REST     /api/orders /api/products
  └─ 审批 API      /api/merchant/tasks
        ↓
Agent 编排 · LangGraph
  ├─ 意图路由    classify
  ├─ 工具节点    product / order / refund
  ├─ 人工中断    human_review（interrupt）
  └─ 响应生成    respond
        ↓
基础设施（本地）
  ├─ PostgreSQL + checkpoint
  └─ oMLX 本地推理（OpenAI 兼容）
```

分层原则：**业务逻辑在 `services/`，Agent 只做编排与语言组织**。
数据库查询不写进 prompt，工具是纯 async 函数，可脱离 LLM 单独单测。

---

## 3. 多租户与角色模型

**租户 = 商家**。用户是平台级消费者，不属于任何租户。

```
智能客服 Demo 平台
├── 商家 A · 租户     商品库 / 订单 / 退款工单 / 审批权   看不到 B 的数据
├── 商家 B · 租户     商品库 / 订单 / 退款工单 / 审批权   看不到 A 的数据
└── 用户 · 消费者     自己的订单 / 自己的退款申请 / 对话入口 /chat
```

两个角色：

| 角色 | 入口 | 可见数据 | 核心动作 |
|---|---|---|---|
| `user` | `/chat` | 仅 `user_id = me` 的订单与退款 | 咨询商品、查订单、申请退款 |
| `merchant` | `/merchant` | 仅 `merchant_id = me` 的商品/订单/退款/工单 | 审批本店退款、查看本店订单 |

隔离实现的三处硬约束：

1. **依赖注入** `get_current_actor()` 解析出 `{role, actor_id, merchant_id}`（demo 级：请求头 `X-Actor-Id`，不做密码）。
2. **查询层强制 scope**：`user` 角色 → `WHERE user_id = me`；`merchant` 角色 → `WHERE merchant_id = me`。
3. **Agent 工具层接收 `scope` 参数**，where 条件由 scope 决定。
   *不做这一步，Agent 会越权检索到别家订单。* 原 `/admin` 人工审批台划归商家端。

---

## 4. 数据模型

### 4.1 表结构

```
merchants
  id, name, slug UNIQUE, created_at

users
  id, name, role CHECK(role IN ('user','merchant')),
  merchant_id FK NULL,          -- role='merchant' 时必填
  created_at

products
  id, merchant_id FK, name, category,
  price NUMERIC(10,2), stock INT, description, created_at

orders
  id, order_no UNIQUE,          -- 格式 #A1001
  user_id FK, merchant_id FK,
  status,                       -- pending/paid/shipped/delivered/cancelled
  total_amount NUMERIC(10,2),
  created_at, shipped_at, delivered_at

order_items
  id, order_id FK, product_id FK, quantity, unit_price NUMERIC(10,2)

refunds
  id, refund_no UNIQUE,         -- 格式 #R2001
  order_id FK, user_id FK, merchant_id FK,
  reason TEXT, amount NUMERIC(10,2),
  status,                       -- draft/pending/approved/rejected/refunded
  review_note TEXT, reviewed_by FK NULL, reviewed_at,
  created_at

conversations
  id, user_id FK, title, created_at, updated_at

messages
  id, conversation_id FK,
  role,                         -- user/assistant/tool/system
  content TEXT,
  widgets JSONB,                -- 前端渲染用结构化数据
  tool_calls JSONB,
  created_at

human_tasks
  id, merchant_id FK,
  thread_id TEXT,               -- = conversation_id，关联 LangGraph checkpoint
  type,                         -- refund_review
  payload JSONB,                -- 快照：订单、金额、原因、触发规则
  status,                       -- pending/approved/rejected
  assignee_id FK NULL,
  created_at, resolved_at
```

LangGraph 的 checkpoint 表由 `AsyncPostgresSaver.setup()` 自动创建，独立 schema，与业务表同库不同前缀。

### 4.2 退款状态机

```
draft ──转人工──→ pending ──商家批准──→ approved ──→ refunded
  │                  └──────商家驳回──→ rejected
  └──自动通过（未触发任何规则）──→ approved ──→ refunded
```

---

## 5. LangGraph Agent 设计

### 5.1 State

```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    actor_role: Literal["user", "merchant"]
    actor_id: int
    merchant_id: int | None          # 租户 scope，工具层强制使用
    intent: Literal["product", "order", "refund", "chitchat", "unknown"]
    order_id: str | None             # 正则抽取的订单号
    refund_draft: dict | None
    human_decision: Literal["approved", "rejected"] | None
    triggering_rule: str | None      # 哪条护栏触发了转人工，展示用
    widgets: list[dict]
    reply: str | None
```

### 5.2 图结构

```
START → classify
classify ├─(product)──→ product_node ─────┐
         ├─(order)────→ order_node ───────┤
         ├─(refund)───→ refund_node → human_review → finalize_refund → respond → END
         ├─(chitchat)─→ chitchat_node ─────┤
         └─(unknown)──→ fallback_node ─────┘
```

- 挂起点只有 `human_review` 一处，`interrupt()` 是唯一的人机边界。
- 未触发转人工规则时，`refund_node` 直接连 `finalize_refund`，跳过 `human_review`。
- Checkpointer：`AsyncPostgresSaver`，`thread_id = conversation_id`。

### 5.3 节点与工具

| 节点 | 职责 | 工具 |
|---|---|---|
| `classify` | 意图识别 + 订单号抽取 | — |
| `product_node` | 商品检索/详情 | `search_products` `get_product_detail` |
| `order_node` | 订单列表/详情/物流 | `list_my_orders` `get_order_detail` |
| `refund_node` | 退款资格校验、建草稿、判定是否转人工 | `check_refund_policy` `create_refund_draft` |
| `human_review` | `interrupt()` 挂起，落库 `human_tasks` | — |
| `finalize_refund` | 批准写库 / 驳回记录原因 | `submit_refund` |
| `respond` | 自然语言 + `widgets` | — |

---

## 6. 人工介入中断恢复闭环

```
① 用户提交退款申请                POST /api/chat/stream（SSE）
② Agent 校验退款策略并建草稿      refunds.status = draft
③ interrupt 挂起，落库待办        human_tasks.status = pending
   SSE 推送 awaiting_human
④ 商家工作台审批：批准或驳回      POST /api/merchant/tasks/{id}/resolve
⑤ Command(resume) 恢复图执行      同一 thread_id
⑥ 写库并答复用户                  refunds.status → refunded / rejected
```

关键点：

- `interrupt()` 抛出后，图状态已由 checkpointer 持久化，进程重启也能恢复。
- 恢复必须传**同一 `thread_id`** 并携带 `Command(resume={"decision": ..., "note": ...})`。
- 挂起期前端每 2s 轮询 `GET /api/conversations/{id}/status`，拿到 `pending_human=false` 即重新拉取消息。
- 不采用长连接等待：实现简单、断线重连零成本、演示不易翻车。

---

## 7. 小模型约束与护栏

`gemma-4-e2b-it-4bit` 约 2B 有效参数 4bit 量化，无法承担多轮工具推理。
因此 **LLM 只负责两件事：意图分类、把结构化数据转成人话**。事实推理全部交给代码。

| 风险 | 护栏 |
|---|---|
| 意图分类不稳定 | 封闭枚举 JSON schema（`product/order/refund/chitchat/unknown`）+ 3–5 个 few-shot，不给开放式指令 |
| 订单号抽取出错 | 正则兜底 `#A\d{4}`，命中则不走模型 |
| 转人工判断错误 | **不让 LLM 判断**，确定性规则写在 `refund_node` 代码里 |
| 输出夹带 markdown fence / 多余文字 | `json_repair` + Pydantic 校验 + 失败重试 1 次，再失败降级规则分支 |

转人工判定规则（`refund_node` 中，纯代码）：

```python
def detect_human_trigger(order, refund_amount, user_text) -> str | None:
    if refund_amount > Decimal("200"):            return "amount_over_threshold"
    if order.status in ("shipped", "delivered"):  return "already_shipped"
    if any(k in user_text for k in ("人工", "客服")): return "user_requested"
    return None
```

---

## 8. API 契约

### 用户端

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/stream` | body `{conversation_id?, message}`，SSE 流式返回 |
| GET | `/api/conversations/{id}` | 拉历史消息 + `widgets` |
| GET | `/api/conversations/{id}/status` | 轮询用，返回 `{pending_human, task_id?}` |
| GET | `/api/orders` | 我的订单（scope: `user_id = me`） |
| GET | `/api/products?q=` | 商品搜索 |

### 商家端

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/merchant/tasks?status=pending` | 本店待审批工单（scope: `merchant_id = me`） |
| POST | `/api/merchant/tasks/{id}/resolve` | body `{decision, note}`，触发图恢复 |
| GET | `/api/merchant/orders` | 本店订单 |

### SSE 事件类型

| `type` | 载荷 | 用途 |
|---|---|---|
| `token` | `{text}` | 增量文本 |
| `tool_call` | `{name, args}` | 展示 Agent 工具调用链（demo 亮点） |
| `widget` | `{kind, data}` | 订单卡 / 退款卡结构化数据 |
| `awaiting_human` | `{task_id}` | 已挂起，前端切换到轮询模式 |
| `done` | `{message_id}` | 本轮结束 |
| `error` | `{message}` | 异常 |

---

## 9. 前端结构

```
src/
├── main.tsx
├── router.tsx                  路由守卫：按 actor.role 拦截
├── lib/
│   ├── api.ts                  fetch 封装，自动注入 X-Actor-Id
│   ├── actor.ts                演示身份（localStorage）
│   └── sse.ts                  流式响应解析
├── hooks/
│   ├── useChatStream.ts
│   └── usePolling.ts           挂起期轮询
├── components/
│   ├── MessageList.tsx
│   ├── MessageBubble.tsx
│   ├── OrderCard.tsx
│   ├── RefundCard.tsx
│   ├── ToolCallTrace.tsx       展示 Agent 每步工具调用
│   ├── StatusBadge.tsx
│   └── RoleSwitcher.tsx
└── pages/
    ├── ChatPage.tsx            /chat
    └── MerchantPage.tsx        /merchant —— 待审批列表 + 本店订单
```

---

## 10. 目录结构

```
smart_service/
├── doc/
│   └── ARCHITECTURE.md
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/       config.py db.py llm.py security.py
│   │   ├── models/     SQLAlchemy ORM
│   │   ├── schemas/    Pydantic DTO
│   │   ├── api/        chat.py orders.py products.py merchant.py
│   │   ├── agent/
│   │   │   ├── graph.py state.py
│   │   │   ├── nodes/  classify.py product.py order.py refund.py human.py respond.py
│   │   │   ├── tools/  纯 async 函数，接收 scope
│   │   │   └── prompts/
│   │   └── services/   业务逻辑，与 Agent 解耦
│   ├── scripts/seed.py
│   └── tests/
└── frontend/
    └── src/           见第 9 节
```

---

## 11. 演示脚本

| 幕 | 操作 | 展示点 |
|---|---|---|
| 1 | 用户端：「你们有蓝牙耳机吗」 | 意图路由 + 商品卡 + 工具调用链 |
| 2 | 用户端：「我的订单到哪了」 | 订单状态卡 |
| 3 | 用户端：「订单 #A1002 我要退款」 | 策略校验 → 触发规则 → 转人工，界面提示「已提交商家审核」 |
| 4 | 切到商家 A 端 | 待办出现该工单，**且看不到商家 B 的**（租户隔离演示）→ 点批准 |
| 5 | 回到用户端 | 轮询拿到结果：「退款已受理，¥XXX 原路退回」 |

预置数据：2 个商家租户、1 个演示用户、约 12 个商品、约 8 条订单（覆盖未发货/已发货/已签收，便于演示不同转人工规则）。

---

## 12. 实施顺序

| 阶段 | 内容 |
|---|---|
| P0 | `uv init` + FastAPI 启动 + PG 连接 + Alembic 初始迁移 |
| P1 | ORM 模型 + `seed.py` 灌 mock 数据 |
| P2 | `agent/tools/` 纯函数 + 单测（不接 LLM，先验证数据正确） |
| P3 | 图骨架：先跑通 product / order 两条分支 |
| P4 | refund 分支 + `human_review` interrupt + 商家端审批 + `Command(resume)` |
| P5 | 前端 `/chat` 流式与卡片 → `/merchant` 审批台 |
| P6 | 串通 5 幕演示脚本 |
