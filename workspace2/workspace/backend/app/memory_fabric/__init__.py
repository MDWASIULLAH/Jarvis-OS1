"""Memory Fabric public API; intentionally independent from legacy ``app.memory``."""

from .manager import MemoryManager
from .models import (
    AgentMemory, ConversationMemory, EpisodicMemory, MemoryAttribute, MemoryDraft,
    MemoryEntry, MemoryExpiration, MemoryMatch, MemoryQuery, MemoryReference,
    MemorySearchResponse, MemoryStatus, MemorySummary, MemoryType, MemoryUpdate,
    ProjectMemory, SemanticMemory, SessionMemory, SharedMemory, UserMemory,
    WorkingMemory, WorkspaceMemory, memory_type_id,
)
from .provider import (
    InMemoryMemoryProvider, MemoryProvider, MemoryProviderContext,
    MemoryProviderMetadata, MemoryProviderRegistry, MemoryVersionConflict,
)

__all__ = [
    "AgentMemory", "ConversationMemory", "EpisodicMemory", "InMemoryMemoryProvider",
    "MemoryAttribute", "MemoryDraft", "MemoryEntry", "MemoryExpiration", "MemoryManager",
    "MemoryMatch", "MemoryProvider", "MemoryProviderContext", "MemoryProviderMetadata",
    "MemoryProviderRegistry", "MemoryQuery", "MemoryReference", "MemorySearchResponse",
    "MemoryStatus", "MemorySummary", "MemoryType", "MemoryUpdate", "MemoryVersionConflict", "memory_type_id",
    "ProjectMemory", "SemanticMemory", "SessionMemory", "SharedMemory", "UserMemory",
    "WorkingMemory", "WorkspaceMemory",
]
