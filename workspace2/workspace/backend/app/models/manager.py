"""The single routing boundary for model-provider requests."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, TypeVar

from .contracts import (
    ModelCapability,
    ModelProvider,
    ModelProviderContext,
    ModelRequest,
    ModelResponse,
    ModelTask,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    StreamingModelResponse,
)
from .registry import ModelProviderRegistry, ProviderFactory


RouteResultT = TypeVar("RouteResultT")


class ModelProviderUnavailable(RuntimeError):
    """No registered provider could safely serve a request."""


class ModelManager:
    """Registry-backed provider selection, fallback, and request routing."""

    def __init__(self, registry: ModelProviderRegistry | None = None, context: ModelProviderContext | None = None) -> None:
        self._registry = registry or ModelProviderRegistry()
        self._registry.initialize(context)

    @property
    def registry(self) -> ModelProviderRegistry:
        return self._registry

    def register_provider(self, metadata: ProviderMetadata, factory: ProviderFactory) -> None:
        self._registry.register(metadata, factory)

    def discover_providers(
        self,
        *,
        capability: ModelCapability | None = None,
        kind: ProviderKind | None = None,
    ) -> tuple[ProviderMetadata, ...]:
        return self._registry.discover(capability=capability, kind=kind)

    def provider_metadata(self, provider_id: str) -> ProviderMetadata:
        return self._registry.metadata(provider_id)

    def health(self, provider_id: str, *, refresh: bool = True) -> ProviderHealth:
        return self._registry.health(provider_id, refresh=refresh)

    def health_snapshot(self, *, refresh: bool = False) -> tuple[tuple[str, ProviderHealth], ...]:
        return self._registry.health_snapshot(refresh=refresh)

    def select_provider(self, request: ModelRequest) -> ModelProvider:
        failures: list[str] = []
        for metadata in self._registry.rank(request):
            try:
                provider = self._registry.get(metadata.provider_id)
                if self._registry.health(metadata.provider_id).status is ProviderHealthStatus.UNHEALTHY:
                    failures.append(f"{metadata.provider_id}: unhealthy")
                    continue
                if provider.supports(request):
                    return provider
                failures.append(f"{metadata.provider_id}: unsupported request")
            except Exception as exc:
                failures.append(f"{metadata.provider_id}: {exc}")
        detail = "; ".join(failures) or "no provider metadata matches request capabilities"
        raise ModelProviderUnavailable(f"No model provider is available: {detail}")

    def generate(self, request: ModelRequest) -> ModelResponse:
        return self._route(request, lambda provider: provider.generate(request))

    def stream_generate(self, request: ModelRequest) -> StreamingModelResponse:
        return self._route(request, lambda provider: provider.stream_generate(request))

    def embeddings(self, texts: tuple[str, ...], request: ModelRequest | None = None) -> tuple[tuple[float, ...], ...]:
        target = replace(request, task=ModelTask.EMBEDDINGS) if request is not None else ModelRequest("", task=ModelTask.EMBEDDINGS)
        return self._route(target, lambda provider: provider.embeddings(texts))

    def tokenize(self, text: str, request: ModelRequest | None = None) -> tuple[str, ...]:
        target = replace(request, task=ModelTask.TOKENIZATION) if request is not None else ModelRequest("", task=ModelTask.TOKENIZATION)
        return self._route(target, lambda provider: provider.tokenize(text))

    def _route(self, request: ModelRequest, invoke: Callable[[ModelProvider], RouteResultT]) -> RouteResultT:
        failures: list[str] = []
        for metadata in self._registry.rank(request):
            try:
                provider = self._registry.get(metadata.provider_id)
                if self._registry.health(metadata.provider_id).status is ProviderHealthStatus.UNHEALTHY or not provider.supports(request):
                    continue
                return invoke(provider)
            except Exception as exc:
                failures.append(f"{metadata.provider_id}: {exc}")
        detail = "; ".join(failures) or "no healthy provider supports request"
        raise ModelProviderUnavailable(f"Model request failed: {detail}")
