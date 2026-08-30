"""Typed provider-neutral search contracts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class SearchCategory(str, Enum):
    GENERAL = "general"
    PROGRAMMING = "programming"
    RESEARCH = "research"
    CURRENT_EVENTS = "current_events"
    DOCUMENTATION = "documentation"
    PEOPLE = "people"
    PLACES = "places"
    IMAGES = "images"
    VIDEOS = "videos"
    CODE = "code"
    PACKAGES = "packages"
    DATASETS = "datasets"
    FILES = "files"


class SearchCapability(str, Enum):
    GENERAL = "general"
    LOCAL = "local"
    DOCUMENTATION = "documentation"
    WEB = "web"
    NEWS = "news"
    ACADEMIC = "academic"
    PACKAGES = "packages"
    IMAGES = "images"
    VIDEOS = "videos"
    FILES = "files"


class SearchProviderHealth(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class SearchAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class SearchQuery:
    text: str
    category: SearchCategory | None = None
    limit: int = 10
    timeout_seconds: float = 5.0
    retry_count: int = 1
    preferred_provider_ids: tuple[str, ...] = ()
    required_capabilities: tuple[SearchCapability, ...] = ()
    correlation_id: str | None = None
    metadata: tuple[SearchAttribute, ...] = ()


@dataclass(frozen=True)
class SearchProviderMetadata:
    provider_id: str
    display_name: str
    capabilities: tuple[SearchCapability, ...]
    priority: int = 0
    dependencies: tuple[str, ...] = ()
    legacy_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchProviderStatus:
    health: SearchProviderHealth
    detail: str = ""


@dataclass(frozen=True)
class SearchCitation:
    source: str
    title: str
    url: str | None = None


@dataclass(frozen=True)
class SearchResult:
    result_id: str
    title: str
    content: str
    source: str
    url: str | None = None
    score: float = 0.0
    confidence: float = 0.0
    citations: tuple[SearchCitation, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[SearchAttribute, ...] = ()

    @classmethod
    def create(cls, title: str, content: str, source: str, **values) -> "SearchResult":
        return cls(str(uuid.uuid4()), title, content, source, **values)


@dataclass(frozen=True)
class SearchFailure:
    provider_id: str
    status: str


@dataclass(frozen=True)
class SearchTelemetry:
    provider_count: int = 0
    duration_seconds: float = 0.0
    cache_hit: bool = False


@dataclass(frozen=True)
class SearchResponse:
    search_id: str
    query: SearchQuery
    results: tuple[SearchResult, ...]
    citations: tuple[SearchCitation, ...]
    failures: tuple[SearchFailure, ...] = ()
    cancelled: bool = False
    telemetry: SearchTelemetry = field(default_factory=SearchTelemetry)
