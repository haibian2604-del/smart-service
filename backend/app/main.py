from fastapi import FastAPI

app = FastAPI(title="Smart Service Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
