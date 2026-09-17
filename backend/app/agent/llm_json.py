import json_repair
from pydantic import BaseModel


def strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        first_newline = t.find("\n")
        if first_newline != -1:
            t = t[first_newline + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


async def ask_json(llm, *, system: str, user: str,
                   schema: type[BaseModel], retries: int = 1) -> BaseModel:
    """complete → 去 fence → json_repair → schema 校验；失败带纠错提示重试。"""
    attempts = retries + 1
    for i in range(attempts):
        raw = await llm.complete(system, user)
        try:
            return schema.model_validate(json_repair.loads(strip_code_fence(raw)))
        except Exception as e:
            last_err = e
    raise ValueError(f"llm_json_failed after {attempts} attempts: {last_err}")
