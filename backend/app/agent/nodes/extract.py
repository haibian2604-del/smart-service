import re

from app.agent.slots import extract_order_no
from app.agent.state import AgentState

# 从自然语句里剥掉疑问/客套词，剩下的当搜索关键词
_NOISE_RE = re.compile(r"你们|请问|我想|想要|看看|有没有|是不是|一下|哪些|什么|多少|钱|价格|买|查|找|有|吗|呢|吧|么|？|\?|。|，|！|！|,|\.|!|\s")


def extract_keyword(text: str) -> str:
    # ponytail: 演示级关键词提取，只做噪音词剥离；不准时升级为 LLM 抽取
    kw = _NOISE_RE.sub("", text)
    return kw


def order_no_in(state: AgentState) -> str | None:
    return state.get("order_no") or extract_order_no(state["text"])
