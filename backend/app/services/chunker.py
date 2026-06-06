import re

import tiktoken

from app.services.ingestion import Chunk, ParsedDocument

_ENCODER = tiktoken.get_encoding("cl100k_base")

_HEADER_RE = re.compile(
    r"^(\d+(\.\d+)+\s+\w)"   # multi-level numbered: "2.3.1 Title"
    r"|^(\d+\.\s+[A-Z])"     # single-level numbered: "2. Title"
    r"|^(#{1,6}\s)"           # markdown: "## Title"
    r"|^[A-Z][A-Z\s]{4,}$"   # ALL CAPS line
)
_LIST_RE = re.compile(r"^(\s*[-*•]|\s*\d+[.)]\s)")


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _classify_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "empty"
    if _HEADER_RE.match(stripped):
        return "header"
    if _LIST_RE.match(stripped):
        return "list_item"
    return "paragraph"


def _table_to_text(table: list[list[str]]) -> str:
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in table)


def _split_to_max(text: str, max_tokens: int) -> list[str]:
    if _count_tokens(text) <= max_tokens:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = (current + " " + sentence).strip()
        if _count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = sentence
    if current:
        parts.append(current)
    # Fallback: word-split if sentence splitting didn't reduce below max_tokens
    final: list[str] = []
    for part in parts:
        if _count_tokens(part) <= max_tokens:
            final.append(part)
        else:
            words = part.split()
            chunk = ""
            for word in words:
                candidate = (chunk + " " + word).strip()
                if _count_tokens(candidate) <= max_tokens:
                    chunk = candidate
                else:
                    if chunk:
                        final.append(chunk)
                    chunk = word
            if chunk:
                final.append(chunk)
    return final or [text[: max_tokens * 4]]


async def chunk_document(
    parsed: ParsedDocument,
    project_id: str,
    min_tokens: int = 50,
    max_tokens: int = 800,
) -> list[Chunk]:
    raw: list[Chunk] = []
    idx = 0
    section_hint = ""

    for page in parsed.pages:
        # Tables first — always atomic
        for table in page.tables:
            table_text = _table_to_text(table)
            if table_text.strip():
                raw.append(Chunk(
                    text=table_text,
                    chunk_index=idx,
                    project_id=project_id,
                    detected_type="table",
                    page_number=page.page_number,
                    section_hint=section_hint,
                    token_count=_count_tokens(table_text),
                ))
                idx += 1

        # Text — group consecutive same-type lines
        current_text = ""
        current_type = "paragraph"

        def flush(t: str, dt: str) -> None:
            nonlocal idx, section_hint
            if not t.strip():
                return
            raw.append(Chunk(
                text=t.strip(),
                chunk_index=idx,
                project_id=project_id,
                detected_type=dt,
                page_number=page.page_number,
                section_hint=section_hint,
                token_count=_count_tokens(t.strip()),
            ))
            if dt == "header":
                section_hint = t.strip()
            idx += 1

        for line in page.text.splitlines():
            lt = _classify_line(line)
            if lt == "empty":
                flush(current_text, current_type)
                current_text = ""
                current_type = "paragraph"
            elif lt != current_type and current_text.strip():
                flush(current_text, current_type)
                current_text = line
                current_type = lt
            else:
                current_text = (current_text + "\n" + line).strip() if current_text else line
                current_type = lt

        flush(current_text, current_type)

    # Size normalization
    final: list[Chunk] = []
    pending: Chunk | None = None

    for chunk in raw:
        if chunk.detected_type == "table":
            if pending:
                final.append(pending)
                pending = None
            final.append(chunk)
            continue

        if chunk.token_count < min_tokens:
            if pending is None:
                pending = chunk
            else:
                merged = pending.text + "\n" + chunk.text
                pending = Chunk(
                    text=merged,
                    chunk_index=pending.chunk_index,
                    project_id=pending.project_id,
                    detected_type=pending.detected_type,
                    page_number=pending.page_number,
                    section_hint=pending.section_hint,
                    token_count=_count_tokens(merged),
                )
        elif chunk.token_count > max_tokens:
            if pending:
                final.append(pending)
                pending = None
            for part in _split_to_max(chunk.text, max_tokens):
                final.append(Chunk(
                    text=part,
                    chunk_index=len(final),
                    project_id=chunk.project_id,
                    detected_type=chunk.detected_type,
                    page_number=chunk.page_number,
                    section_hint=chunk.section_hint,
                    token_count=_count_tokens(part),
                ))
        else:
            if pending:
                final.append(pending)
                pending = None
            final.append(chunk)

    if pending:
        final.append(pending)

    for i, c in enumerate(final):
        c.chunk_index = i

    return final
