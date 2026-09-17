from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, merchant


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: API 测试走 MemorySaver（conftest 注入 app.state）；生产 P6 再切 AsyncPostgresSaver
    app.state.checkpointer = None
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
