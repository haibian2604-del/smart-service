"""工具名 → 纯 async 函数的查表注册。工具在各模块实现后在此汇总。"""

TOOLS: dict = {}


def register(name: str):
    def deco(fn):
        TOOLS[name] = fn
        return fn
    return deco
