# smart-service · 智能客服 Agent 系统（开发中）

一个用于演示 **Agent 能力** 的智能客服系统：意图路由、工具调用、人工介入与中断恢复。

> **当前状态：设计阶段。** 架构与实施计划已完成，代码尚未开始编写。

---

## 核心能力

| 能力 | 说明 |
|---|---|
| 商品咨询 | 用户用自然语言询问商品，Agent 检索并返回商品卡片 |
| 订单查询 | 查询订单状态与物流，返回订单卡片 |
| 退款申请 | 校验退款资格；命中规则时**挂起为人工工单** |
| 人工介入 | 商家在工作台审批，Agent 从挂起点**恢复执行**并答复用户 |
| 多租户隔离 | 商家之间数据严格隔离，隔离在工具层强制生效 |

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI · uv · LangGraph · SQLAlchemy 2.x · Alembic |
| 前端 | Vite · React 19 · TypeScript · Tailwind CSS v4 · React Router |
| 测试 | Vitest + React Testing Library（前端）· Pytest（后端） |
| 数据库 | PostgreSQL 16（业务表与 LangGraph checkpoint 同库） |
| LLM | 本地 oMLX `gemma-4-e2b-it-4bit`，OpenAI 兼容接口 |

## 架构

```
前端 (React) ──HTTP / SSE──▶ 后端 (FastAPI) ──▶ Agent 编排 (LangGraph) ──▶ PostgreSQL
                                                      │
                                                      └──▶ oMLX 本地推理
```

Agent 图：

```
START → classify ─┬─ product  ─────────────────────▶ respond → END
                  ├─ order    ─────────────────────▶ respond → END
                  ├─ refund   ─┬─ 无触发 ──────────▶ respond → END
                  │            └─ 有触发 ─▶ human_review → finalize_refund → respond → END
                  ├─ chitchat ─────────────────────▶ respond → END
                  └─ unknown  ─────────────────────▶ respond → END
```

退款申请的人工介入闭环：

```
① 用户提交退款申请
② Agent 校验退款策略并建草稿            refunds.status = draft
③ interrupt 挂起，落库待办              human_tasks.status = pending
④ 商家工作台审批：批准或驳回
⑤ Command(resume) 恢复图执行            同一 thread_id
⑥ 写库并答复用户                        refunds.status → refunded / rejected
```

详见 [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md)。

## 多租户与角色

租户 = 商家。用户是平台级消费者，不属于任何租户。

| 角色 | 入口 | 可见数据 | 核心动作 |
|---|---|---|---|
| `user` | `/chat` | 仅自己的订单与退款申请 | 咨询商品、查订单、申请退款 |
| `merchant` | `/merchant` | 仅本店的商品、订单、退款工单 | 审批本店退款、查看本店订单 |

租户过滤在 **Agent 工具层的 where 条件内**强制生效，而不是先查询再校验。
若只在 API 层过滤，Agent 调用订单工具时仍可能读到其他商家的订单。

## 关键设计约束

目标模型是本地小模型（约 2B 有效参数、4bit 量化），因此 **LLM 只承担两件事**：
意图分类、把结构化数据转成自然语言。事实推理与规则判定全部由代码承担。

| 风险 | 护栏 |
|---|---|
| 意图分类不稳定 | 封闭枚举 JSON schema + few-shot，不给开放式指令 |
| 订单号抽取出错 | 正则兜底，命中即不走模型 |
| 转人工判断错误 | 确定性规则写在代码里，不让 LLM 判断 |
| 输出格式不合规 | `json_repair` + Pydantic 校验 + 重试，再失败降级到规则分支 |

## 文档

| 文件 | 内容 |
|---|---|
| [`doc/ARCHITECTURE.md`](doc/ARCHITECTURE.md) | 系统架构设计：分层、数据模型、Agent 图、API 契约 |
| [`doc/plans/2026-09-17-smart-service-implementation.md`](doc/plans/2026-09-17-smart-service-implementation.md) | 32 任务实施计划，逐任务 TDD 步骤 |

## 开发进度

| 阶段 | 状态 |
|---|---|
| 架构设计 | 已完成 |
| 实施计划 | 已完成 |
| P0 脚手架 | ✅ 已完成 |
| P1 数据层 | ✅ 已完成 |
| P2 工具层 | ✅ 已完成 |
| P3 Agent 图 | ✅ 已完成 |
| P4 API 层 | ✅ 已完成 |
| P5 前端 | ✅ 已完成 |
| P6 端到端串通 | ✅ 已完成 |

## 快速开始

见 [`doc/RUNBOOK.md`](doc/RUNBOOK.md)：oMLX 启动 → `make db-up migrate seed api web` → 五幕演示。

```bash
make db-up && make migrate && make seed
make api    # 注意与 oMLX 端口冲突，见 RUNBOOK
make web
```

## 目录结构

```
smart-service/
├── README.md
├── doc/
│   ├── ARCHITECTURE.md
│   └── plans/
├── backend/          # FastAPI + LangGraph（101 tests green，含五幕端到端）
│   ├── app/core/         # config / db / llm（oMLX 已连通）
│   ├── app/models/       # 9 张 ORM 表
│   ├── app/agent/        # 图组装 / classify·refund·human_review 等节点 / 7 工具
│   ├── app/api/          # SSE 对话流 · 会话轮询 · 商家审批（interrupt/resume 闭环已跑通）
│   ├── alembic/          # 异步迁移
│   ├── scripts/seed.py   # 幂等演示数据
│   └── tests/            # 39 个测试（FakeLLM 策略，事务回滚隔离）
└── frontend/         # Vite + React（待建）
```
