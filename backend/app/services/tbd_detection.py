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

_L3_PROMPT = """You are reviewing a software requirements document for completeness.
The document has the following sections (extracted from chunk metadata):
{present_sections}

Required sections for a complete SRS document:
{required_sections}

Identify which required sections are ABSENT or not meaningfully covered by the present sections.
A section is "covered" if any present section is clearly equivalent or a superset (e.g. "auth" covers "authentication").
Return ONLY a JSON object: {{"items": [{{"section": str, "reason": str}}]}}
Return {{"items": []}} if all required sections are present."""

_L4_PROMPT = """You are reviewing a software requirements document for internal contradictions.

Requirements document (chunked):
{chunks}

Identify pairs of requirements that directly contradict each other.
A contradiction means two requirements cannot both be satisfied simultaneously.
Examples: "must be offline-capable" vs "requires always-on cloud sync";
          "response time < 100ms" in one section vs "batch processing acceptable" in another.

For each contradiction, write a short label in "text" (e.g. "Offline mode vs cloud sync requirement")
and a clear explanation in "reason".

Return ONLY a JSON object: {{"items": [{{"text": str, "reason": str}}]}}
Return {{"items": []}} if no contradictions found."""

_REQUIRED_SECTIONS = [
    "authentication",
    "authorization",
    "security",
    "performance",
    "error handling",
    "api design",
    "data model",
    "deployment",
    "monitoring",
    "scalability",
]

_LEVEL_TO_TBD_LEVEL = {
    1: "explicit",
    2: "vague",
    3: "missing_section",
    4: "contradiction",
}

_L4_MAX_CHARS = 40_000


class _TBDItem(BaseModel):
    text: str
    reason: str
    level: Literal[1, 2, 3, 4]


class _TBDResult(BaseModel):
    items: list[_TBDItem]


class _MissingSection(BaseModel):
    section: str
    reason: str


class _MissingSectionResult(BaseModel):
    items: list[_MissingSection]


class _Contradiction(BaseModel):
    text: str
    reason: str


class _ContradictionResult(BaseModel):
    items: list[_Contradiction]


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


async def detect_level_3(chunks: list[dict]) -> list[dict]:
    if not chunks:
        return []
    present = {
        c.get("section_hint", "").strip().lower()
        for c in chunks
        if c.get("section_hint")
    }
    present_str = ", ".join(sorted(present)) or "(none detected)"
    required_str = ", ".join(_REQUIRED_SECTIONS)

    llm = get_fast_llm()
    structured = llm.with_structured_output(_MissingSectionResult)
    result: _MissingSectionResult = cast(
        _MissingSectionResult,
        await structured.ainvoke([
            HumanMessage(content=_L3_PROMPT.format(
                present_sections=present_str,
                required_sections=required_str,
            ))
        ]),
    )
    return [
        {"text": item.section, "reason": item.reason, "level": 3}
        for item in result.items
    ]


async def detect_level_4(
    chunks: list[dict],
    known_tbds: set[str] | None = None,
) -> list[dict]:
    if not chunks:
        return []
    known = known_tbds or set()
    combined = "\n\n---\n\n".join(
        f"[{c.get('section_hint', '')}] {c['text']}" for c in chunks
    )
    if len(combined) > _L4_MAX_CHARS:
        combined = combined[:_L4_MAX_CHARS]

    llm = get_fast_llm()
    structured = llm.with_structured_output(_ContradictionResult)
    result: _ContradictionResult = cast(
        _ContradictionResult,
        await structured.ainvoke([HumanMessage(content=_L4_PROMPT.format(chunks=combined))]),
    )
    return [
        {"text": item.text, "reason": item.reason, "level": 4}
        for item in result.items
        if item.text not in known
    ]


def persist_tbds(project_id: int, tbds: list[dict]) -> None:
    from app.database import SessionLocal
    from app.models.clarification import Clarification
    from app.models.enums import TBDLevel, TBDStatus

    if not tbds:
        return

    db = SessionLocal()
    try:
        existing_titles = {
            row.title
            for row in db.query(Clarification.title)
                         .filter(Clarification.project_id == project_id)
                         .all()
        }
        for tbd in tbds:
            title = tbd["text"]
            if title in existing_titles:
                continue
            level_str = _LEVEL_TO_TBD_LEVEL.get(tbd.get("level", 1), "explicit")
            row = Clarification(
                project_id=project_id,
                title=title,
                description=tbd.get("reason", ""),
                level=TBDLevel(level_str),
                status=TBDStatus.open,
            )
            db.add(row)
        db.commit()
    finally:
        db.close()


async def detect_tbds(
    query: str,
    chunks: list[dict],
    known_tbds: set[str] | None = None,
    run_deep: bool = False,
) -> list[dict]:
    known = known_tbds or set()
    level1 = [t for t in detect_level_1(query) if t["text"] not in known]
    level2 = await detect_level_2_batch(chunks, known_tbds=known)
    all_tbds = level1 + level2

    if run_deep:
        level3 = await detect_level_3(chunks)
        level4 = await detect_level_4(chunks, known_tbds=known)
        all_tbds = all_tbds + level3 + level4

    return list({t["text"]: t for t in all_tbds}.values())
