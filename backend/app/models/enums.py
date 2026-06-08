from enum import Enum


class ProjectStatus(str, Enum):
    draft = "draft"
    active = "active"
    complete = "complete"
    archived = "archived"


class ProjectPhase(str, Enum):
    redaction = "redaction"
    chat = "chat"
    modules = "modules"
    techstack = "techstack"
    team = "team"
    estimation = "estimation"
    epics = "epics"
    complete = "complete"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    anonymising = "anonymising"
    ready = "ready"


class TBDLevel(str, Enum):
    explicit = "explicit"
    vague = "vague"
    missing_section = "missing_section"
    contradiction = "contradiction"


class TBDStatus(str, Enum):
    open = "open"
    answered = "answered"
    tbd = "tbd"
    oos = "oos"


class TBDAction(str, Enum):
    answer = "Answer"
    tbd = "TBD"
    out_of_scope = "Out-of-Scope"


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"
    skipped = "skipped"
    failed = "failed"
