"""Typed, provider-neutral contracts for all language-model access."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderKind(str, Enum):
    LOCAL = "local"
    EMBEDDED = "embedded"
    REMOTE = "remote"
    LEGACY = "legacy"


class ModelCapability(str, Enum):
    CHAT = "chat"
    CODING = "coding"
    REASONING = "reasoning"
    VISION = "vision"
    TRANSLATION = "translation"
    EMBEDDINGS = "embeddings"
    TOKENIZATION = "tokenization"
    STREAMING = "streaming"


class ModelTask(str, Enum):
    GENERAL = "general"
    CODING = "coding"
    REASONING = "reasoning"
    VISION = "vision"
    TRANSLATION = "translation"
    EMBEDDINGS = "embeddings"
    TOKENIZATION = "tokenization"


class ProviderHealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class ModelAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    display_name: str
    model_name: str
    kind: ProviderKind
    capabilities: tuple[ModelCapability, ...]
    priority: int = 0
    estimated_cost_per_1k_tokens: float = 0.0
    estimated_latency_ms: float = 0.0
    legacy_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderHealth:
    status: ProviderHealthStatus
    detail: str = ""
    checked_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    system_prompt: str | None = None
    task: ModelTask = ModelTask.GENERAL
    required_capabilities: tuple[ModelCapability, ...] = ()
    preferred_provider_ids: tuple[str, ...] = ()
    fallback_provider_ids: tuple[str, ...] = ()
    prefer_local: bool = True
    max_tokens: int | None = None
    temperature: float | None = None
    correlation_id: str | None = None
    metadata: tuple[ModelAttribute, ...] = ()

    @property
    def all_required_capabilities(self) -> tuple[ModelCapability, ...]:
        task_capability = {
            ModelTask.GENERAL: ModelCapability.CHAT,
            ModelTask.CODING: ModelCapability.CODING,
            ModelTask.REASONING: ModelCapability.REASONING,
            ModelTask.VISION: ModelCapability.VISION,
            ModelTask.TRANSLATION: ModelCapability.TRANSLATION,
            ModelTask.EMBEDDINGS: ModelCapability.EMBEDDINGS,
            ModelTask.TOKENIZATION: ModelCapability.TOKENIZATION,
        }[self.task]
        return tuple(dict.fromkeys((task_capability, *self.required_capabilities)))


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class GenerationMetrics:
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    provider_id: str = ""


@dataclass(frozen=True)
class ModelResponse:
    provider_id: str
    model_name: str
    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    metrics: GenerationMetrics = field(default_factory=GenerationMetrics)
    metadata: tuple[ModelAttribute, ...] = ()


@dataclass(frozen=True)
class ModelResponseChunk:
    provider_id: str
    sequence: int
    content: str
    is_final: bool = False


@dataclass(frozen=True)
class StreamingModelResponse:
    provider_id: str
    model_name: str
    chunks: tuple[ModelResponseChunk, ...]
    usage: TokenUsage = field(default_factory=TokenUsage)
    metrics: GenerationMetrics = field(default_factory=GenerationMetrics)

    def __iter__(self):
        return iter(self.chunks)


class ModelProviderContext:
    """Dependency-injection boundary for lazy model-provider initialization."""

    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Model provider dependency is unavailable: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self._services


class ModelProvider(ABC):
    """All local, embedded, remote, and future providers share this surface."""

    @abstractmethod
    def initialize(self, context: ModelProviderContext) -> None:
        ...

    @abstractmethod
    def shutdown(self) -> None:
        ...

    @abstractmethod
    def health(self) -> ProviderHealth:
        ...

    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        ...

    @abstractmethod
    def supports(self, request: ModelRequest) -> bool:
        ...

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        ...

    @abstractmethod
    def stream_generate(self, request: ModelRequest) -> StreamingModelResponse:
        ...

    @abstractmethod
    def embeddings(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        ...

    @abstractmethod
    def tokenize(self, text: str) -> tuple[str, ...]:
        ...

    @abstractmethod
    def estimate_cost(self, request: ModelRequest) -> float:
        ...

    @abstractmethod
    def estimate_latency(self, request: ModelRequest) -> float:
        ...
