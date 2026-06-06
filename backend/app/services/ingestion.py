from dataclasses import dataclass, field


@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    filename: str
    pages: list[PageContent]


@dataclass
class Chunk:
    text: str
    chunk_index: int
    project_id: str
    detected_type: str   # "paragraph" | "header" | "table" | "list_item"
    page_number: int
    section_hint: str
    token_count: int
