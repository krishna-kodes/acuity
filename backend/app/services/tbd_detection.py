import re
from typing import Literal, cast

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.services.llm_factory import get_fast_llm

_L1_RE = re.compile(
    r"\b(TBD|TODO|N/?A|to be determined|to be confirmed|TBC|UNKNOWN|unclear|not yet defined)\b",
    re.IGNORECASE,
)

_L2_PROMPT = """You are reviewing requirements document chunks for quality issues.
Identify any statements that are vague, unmeasurable, or lack clear criteria.
Examples: "should be fast", "must be reliable", "easy to use", "as needed".
Return ONLY a JSON object: {{"items": [{{"text": str, "reason": str, "level": 2}}]}}
Return {{"items": []}} if none found.

Document chunks:
{chunks}"""


class _TBDItem(BaseModel):
    text: str
    reason: str
    level: Literal[1, 2]


class _TBDResult(BaseModel):
    items: list[_TBDItem]


def detect_level_1(text: str) -> list[dict]:
    return [
        {"text": m.group(), "reason": "Explicit placeholder or unknown", "level": 1}
        for m in _L1_RE.finditer(text)
    ]


async def detect_level_2_batch(
    chunks: list[dict],
    known_tbds: set[str] | None = None,
) -> list[dict]:
    if not chunks:
        return []
    known = known_tbds or set()
    combined = "\n\n---\n\n".join(c["text"] for c in chunks)
    llm = get_fast_llm()
    structured = llm.with_structured_output(_TBDResult)
    result: _TBDResult = cast(
        _TBDResult,
        await structured.ainvoke([HumanMessage(content=_L2_PROMPT.format(chunks=combined))]),
    )
    return [
        item.model_dump()
        for item in result.items
        if item.text not in known
    ]


async def detect_tbds(
    query: str,
    chunks: list[dict],
    known_tbds: set[str] | None = None,
) -> list[dict]:
    known = known_tbds or set()
    level1 = [t for t in detect_level_1(query) if t["text"] not in known]
    level2 = await detect_level_2_batch(chunks, known_tbds=known)
    all_tbds = level1 + level2
    return list({t["text"]: t for t in all_tbds}.values())
