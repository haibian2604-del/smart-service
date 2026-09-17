# RUNBOOK — 本地启动与演示手册

## 前置条件

- Docker（pgvector 容器）
- `uv` ≥ 0.11
- Node ≥ 22 + `pnpm`
- oMLX 本地推理服务（含 `gemma-4-e2b-it-4bit`）

## 1. 启动 oMLX

```bash
mlx_lm.server --model <模型路径>/gemma-4-e2b-it-4bit --port 8000
```

- 监听 `:8000`，OpenAI 兼容 `/v1`
- 项目 `backend/.env` 默认指向 `http://127.0.0.1:8000/v1`，API Key 用 `sk-omlx-...`
- **LLM 不在线也能演示**：意图分类有关键词兜底（`degraded` 模式），仅少自然语言组织

## 2. 启动数据库并初始化

```bash
make db-up        # 启动 pgvector 容器（:5432，postgres/123456）
make migrate      # alembic 建表（9 张业务表）
make seed         # 灌演示数据：2 商家 / 1 用户 / 12 商品 / 8 订单
```

## 3. 启动服务

```bash
make api          # 后端 :8000 …… 注意：与 oMLX 端口冲突！
```

> **端口冲突处理**：后端默认 `:8000`。若 oMLX 已占 8000，改用：
> ```bash
> cd backend && uv run uvicorn app.main:app --reload --port 8001
> ```
> 并把 `frontend/vite.config.ts` 的 proxy 目标同步改为 `http://127.0.0.1:8001`。
> （或者反过来让 oMLX 换端口，同步 `LLM_BASE_URL`。）

```bash
make web          # 前端 :5173，/api 已代理到后端
```

## 4. 演示身份

| 身份 | actor id | 入口 |
|---|---|---|
| 演示用户（消费者） | 1 | `/chat` |
| 青柠数码（租户 #1） | 2 | `/merchant` |
| 山野户外（租户 #2） | 3 | `/merchant` |

打开 `http://localhost:5173` → 选择身份即自动进入对应工作台。

## 5. 五幕演示脚本

| 幕 | 操作 | 预期 |
|---|---|---|
| 1 | 用户端输入或点快捷「你们有蓝牙耳机吗」 | 工具调用链 + 商品卡 |
| 2 | 「我的订单 #A1002 到哪了」 | 订单卡（已付款 ¥199） |
| 3 | 「订单 #A1002 我要退款」 | 策略校验 → 触发「已发货/签收」规则 → 琥珀横幅「已转人工」 |
| 4 | 切换身份到青柠数码 | 待审批列表有该工单（金额/原因/触发规则）；**切到山野户外则看不到** → 回青柠数码点「批准」 |
| 5 | 切回用户端 | 横幅消失，最新回复「退款申请已通过，¥599.00 将原路退回」+ 退款卡全绿 |

补充演示点：`#A1001`（¥199 已付款）退款会**自动通过**，不转人工——展示规则分支。

## 6. 测试

```bash
make test         # 后端 99 pytest + 前端 29 vitest
```

后端测试永不调用真实 LLM（FakeLLM/SmartFakeLLM），无需 oMLX 在线。
