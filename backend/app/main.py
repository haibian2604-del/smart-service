from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, merchant


@asynccontextmanager
async def lifespan(app: FastAPI):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from app.core.config import get_settings

    dsn = get_settings().database_url.replace("+asyncpg", "")
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()  # 幂等建 checkpoint 表
        app.state.checkpointer = saver
        yield


app = FastAPI(title="Smart Service Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(merchant.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
