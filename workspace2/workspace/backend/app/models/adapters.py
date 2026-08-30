"""Compatibility adapters for JARVIS's established LLMBackend interface."""

from __future__ import annotations

import time
from typing import Any

from .contracts import (
    GenerationMetrics,
    ModelCapability,
    ModelProvider,
    ModelProviderContext,
    ModelRequest,
    ModelResponse,
    ModelResponseChunk,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderMetadata,
    StreamingModelResponse,
    TokenUsage,
)


class LegacyLLMProviderAdapter(ModelProvider):
    """Adapts pre-Phase-8 backends without changing their public interface."""

    def __init__(self, backend: Any, metadata: ProviderMetadata) -> None:
        self._backend = backend
        self._metadata = metadata

    def initialize(self, context: ModelProviderContext) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def health(self) -> ProviderHealth:
        available = bool(self._backend.is_available())
        return ProviderHealth(ProviderHealthStatus.HEALTHY if available else ProviderHealthStatus.UNHEALTHY)

    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def supports(self, request: ModelRequest) -> bool:
        return set(request.all_required_capabilities).issubset(self._metadata.capabilities)

    def generate(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        content = self._backend.generate(request.prompt, request.system_prompt)
        usage = TokenUsage(len(request.prompt.split()), len(content.split()))
        metrics = GenerationMetrics((time.monotonic() - started) * 1_000, self.estimate_cost(request), self._metadata.provider_id)
        return ModelResponse(self._metadata.provider_id, self._metadata.model_name, content, usage, metrics)

    def stream_generate(self, request: ModelRequest) -> StreamingModelResponse:
        started = time.monotonic()
        chunks = tuple(
            ModelResponseChunk(self._metadata.provider_id, index, content)
            for index, content in enumerate(self._backend.generate_stream(request.prompt, request.system_prompt))
        )
        if chunks:
            chunks = (*chunks[:-1], ModelResponseChunk(chunks[-1].provider_id, chunks[-1].sequence, chunks[-1].content, True))
        else:
            chunks = (ModelResponseChunk(self._metadata.provider_id, 0, "", True),)
        content = "".join(item.content for item in chunks)
        return StreamingModelResponse(
            self._metadata.provider_id,
            self._metadata.model_name,
            chunks,
            TokenUsage(len(request.prompt.split()), len(content.split())),
            GenerationMetrics((time.monotonic() - started) * 1_000, self.estimate_cost(request), self._metadata.provider_id),
        )

    def embeddings(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return ()

    def tokenize(self, text: str) -> tuple[str, ...]:
        return tuple(text.split())

    def estimate_cost(self, request: ModelRequest) -> float:
        return (len(request.prompt.split()) / 1_000) * self._metadata.estimated_cost_per_1k_tokens

    def estimate_latency(self, request: ModelRequest) -> float:
        return self._metadata.estimated_latency_ms
