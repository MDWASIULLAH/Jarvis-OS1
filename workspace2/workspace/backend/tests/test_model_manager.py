from __future__ import annotations

from app.brain.llm_interface import MockBackend
from app.models import (
    GenerationMetrics,
    LegacyLLMProviderAdapter,
    ModelCapability,
    ModelManager,
    ModelProvider,
    ModelProviderContext,
    ModelRequest,
    ModelResponse,
    ModelResponseChunk,
    ModelTask,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    StreamingModelResponse,
    TokenUsage,
)


class FakeProvider(ModelProvider):
    def __init__(self, metadata: ProviderMetadata, *, health: ProviderHealthStatus = ProviderHealthStatus.HEALTHY, fail: bool = False) -> None:
        self._metadata = metadata
        self._health = health
        self._fail = fail
        self.initialized = 0
        self.shutdowns = 0

    def initialize(self, context: ModelProviderContext) -> None:
        self.initialized += 1

    def shutdown(self) -> None:
        self.shutdowns += 1

    def health(self) -> ProviderHealth:
        return ProviderHealth(self._health)

    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def supports(self, request: ModelRequest) -> bool:
        return set(request.all_required_capabilities).issubset(self._metadata.capabilities)

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self._fail:
            raise RuntimeError("provider failed")
        return ModelResponse(self._metadata.provider_id, self._metadata.model_name, f"{self._metadata.provider_id}:{request.prompt}", TokenUsage(1, 1), GenerationMetrics(provider_id=self._metadata.provider_id))

    def stream_generate(self, request: ModelRequest) -> StreamingModelResponse:
        chunks = (
            ModelResponseChunk(self._metadata.provider_id, 0, "hello "),
            ModelResponseChunk(self._metadata.provider_id, 1, "world", True),
        )
        return StreamingModelResponse(self._metadata.provider_id, self._metadata.model_name, chunks)

    def embeddings(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((float(len(text)),) for text in texts)

    def tokenize(self, text: str) -> tuple[str, ...]:
        return tuple(text.split())

    def estimate_cost(self, request: ModelRequest) -> float:
        return 0.0

    def estimate_latency(self, request: ModelRequest) -> float:
        return 1.0


def _metadata(provider_id: str, *capabilities: ModelCapability, priority: int = 0, kind: ProviderKind = ProviderKind.LOCAL) -> ProviderMetadata:
    return ProviderMetadata(provider_id, provider_id, provider_id + "-model", kind, capabilities, priority=priority)


def test_provider_registration_discovery_and_lazy_loading():
    manager = ModelManager()
    metadata = _metadata("local", ModelCapability.CHAT)
    instances: list[FakeProvider] = []

    def factory(context: ModelProviderContext) -> FakeProvider:
        provider = FakeProvider(metadata)
        instances.append(provider)
        return provider

    manager.register_provider(metadata, factory)

    assert manager.discover_providers(capability=ModelCapability.CHAT) == (metadata,)
    assert instances == []

    response = manager.generate(ModelRequest("hello"))
    assert response.content == "local:hello"
    assert instances[0].initialized == 1


def test_capability_based_routing_selects_best_matching_provider():
    manager = ModelManager()
    general = _metadata("general", ModelCapability.CHAT, priority=100)
    coding = _metadata("coding", ModelCapability.CHAT, ModelCapability.CODING, priority=10)
    manager.register_provider(general, lambda context: FakeProvider(general))
    manager.register_provider(coding, lambda context: FakeProvider(coding))

    response = manager.generate(ModelRequest("write a function", task=ModelTask.CODING))

    assert response.provider_id == "coding"


def test_health_monitoring_and_generation_failure_fall_back_to_next_provider():
    manager = ModelManager()
    unhealthy = _metadata("unhealthy", ModelCapability.CHAT, priority=100)
    failing = _metadata("failing", ModelCapability.CHAT, priority=90)
    fallback = _metadata("fallback", ModelCapability.CHAT, priority=10)
    manager.register_provider(unhealthy, lambda context: FakeProvider(unhealthy, health=ProviderHealthStatus.UNHEALTHY))
    manager.register_provider(failing, lambda context: FakeProvider(failing, fail=True))
    manager.register_provider(fallback, lambda context: FakeProvider(fallback))

    response = manager.generate(ModelRequest("hello"))
    snapshot = dict(manager.health_snapshot())

    assert response.provider_id == "fallback"
    assert snapshot["unhealthy"].status is ProviderHealthStatus.UNHEALTHY


def test_streaming_response_is_typed_and_ordered():
    manager = ModelManager()
    metadata = _metadata("stream", ModelCapability.CHAT, ModelCapability.STREAMING)
    manager.register_provider(metadata, lambda context: FakeProvider(metadata))

    response = manager.stream_generate(ModelRequest("hello", required_capabilities=(ModelCapability.STREAMING,)))

    assert "".join(chunk.content for chunk in response) == "hello world"
    assert response.chunks[-1].is_final is True


def test_legacy_backend_adapter_preserves_existing_generate_and_streaming_interfaces():
    metadata = _metadata("legacy", ModelCapability.CHAT, ModelCapability.STREAMING)
    adapter = LegacyLLMProviderAdapter(MockBackend(), metadata)
    adapter.initialize(ModelProviderContext())

    response = adapter.generate(ModelRequest("hello"))
    streamed = adapter.stream_generate(ModelRequest("hello", required_capabilities=(ModelCapability.STREAMING,)))

    assert response.content.startswith("[mock response]")
    assert "".join(chunk.content for chunk in streamed).startswith("[mock response]")
    assert adapter.tokenize("one two") == ("one", "two")


def test_embedding_and_tokenization_routes_can_select_specialized_providers():
    manager = ModelManager()
    embeddings = _metadata("embeddings", ModelCapability.EMBEDDINGS, priority=10)
    tokens = _metadata("tokens", ModelCapability.TOKENIZATION, priority=10)
    manager.register_provider(embeddings, lambda context: FakeProvider(embeddings))
    manager.register_provider(tokens, lambda context: FakeProvider(tokens))

    assert manager.embeddings(("abc", "de")) == ((3.0,), (2.0,))
    assert manager.tokenize("one two") == ("one", "two")
