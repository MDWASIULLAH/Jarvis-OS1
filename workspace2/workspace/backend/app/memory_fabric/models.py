"""Immutable, provider-neutral contracts for the Memory Fabric."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MemoryType(str, Enum):
    WORKING = "working"
    SESSION = "session"
    CONVERSATION = "conversation"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROJECT = "project"
    WORKSPACE = "workspace"
    USER = "user"
    AGENT = "agent"
    SHARED = "shared"


MemoryKind = MemoryType | str


def memory_type_id(memory_type: MemoryKind) -> str:
    """Normalize built-in enums and provider-defined future memory kinds."""
    return memory_type.value if isinstance(memory_type, MemoryType) else memory_type


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass(frozen=True)
class MemoryAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class MemoryReference:
    identifier: str
    kind: str = "memory"


@dataclass(frozen=True)
class MemoryExpiration:
    expires_at: datetime | None = None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True)
class MemoryEntry:
    memory_id: str
    memory_type: MemoryKind
    title: str
    content: str
    summary: str = ""
    embedding: tuple[float, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[MemoryAttribute, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    confidence: float = 1.0
    importance: float = 0.5
    access_frequency: int = 0
    expiration: MemoryExpiration = field(default_factory=MemoryExpiration)
    owner_id: str | None = None
    permissions: tuple[str, ...] = ()
    references: tuple[MemoryReference, ...] = ()
    version: int = 1
    status: MemoryStatus = MemoryStatus.ACTIVE
    archived_at: datetime | None = None
    knowledge_entity_id: str | None = None


# Named types make memory intent explicit while retaining one portable entry contract.
@dataclass(frozen=True, kw_only=True)
class WorkingMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.WORKING, init=False)


@dataclass(frozen=True, kw_only=True)
class SessionMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.SESSION, init=False)


@dataclass(frozen=True, kw_only=True)
class ConversationMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.CONVERSATION, init=False)


@dataclass(frozen=True, kw_only=True)
class EpisodicMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.EPISODIC, init=False)


@dataclass(frozen=True, kw_only=True)
class SemanticMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.SEMANTIC, init=False)


@dataclass(frozen=True, kw_only=True)
class ProjectMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.PROJECT, init=False)


@dataclass(frozen=True, kw_only=True)
class WorkspaceMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.WORKSPACE, init=False)


@dataclass(frozen=True, kw_only=True)
class UserMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.USER, init=False)


@dataclass(frozen=True, kw_only=True)
class AgentMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.AGENT, init=False)


@dataclass(frozen=True, kw_only=True)
class SharedMemory(MemoryEntry):
    memory_type: MemoryType = field(default=MemoryType.SHARED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryDraft:
    memory_type: MemoryKind
    title: str
    content: str
    summary: str = ""
    embedding: tuple[float, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[MemoryAttribute, ...] = ()
    source: str = ""
    confidence: float = 1.0
    importance: float = 0.5
    expiration: MemoryExpiration = field(default_factory=MemoryExpiration)
    owner_id: str | None = None
    permissions: tuple[str, ...] = ()
    references: tuple[MemoryReference, ...] = ()
    knowledge_entity_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class MemoryUpdate:
    expected_version: int
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    embedding: tuple[float, ...] | None = None
    tags: tuple[str, ...] | None = None
    metadata: tuple[MemoryAttribute, ...] | None = None
    confidence: float | None = None
    importance: float | None = None
    expiration: MemoryExpiration | None = None
    owner_id: str | None = None
    permissions: tuple[str, ...] | None = None
    references: tuple[MemoryReference, ...] | None = None


@dataclass(frozen=True, kw_only=True)
class MemoryQuery:
    text: str = ""
    memory_types: tuple[MemoryKind, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[MemoryAttribute, ...] = ()
    project_id: str | None = None
    workspace_id: str | None = None
    user_id: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    include_archived: bool = False
    semantic: bool = False
    limit: int = 20


@dataclass(frozen=True)
class MemoryMatch:
    memory: MemoryEntry
    score: float


@dataclass(frozen=True)
class MemorySearchResponse:
    matches: tuple[MemoryMatch, ...]
    external_search_used: bool = False


@dataclass(frozen=True)
class MemorySummary:
    memory_id: str
    summary: str


def memory_id() -> str:
    return str(uuid.uuid4())
