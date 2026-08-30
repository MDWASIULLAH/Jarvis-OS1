from __future__ import annotations

import time

from app.events.bus import EventBus
from app.events.model import EventType
from app.search import (
    CallableSearchProviderAdapter,
    SearchCancellationToken,
    SearchCapability,
    SearchManager,
    SearchProvider,
    SearchProviderContext,
    SearchProviderHealth,
    SearchProviderMetadata,
    SearchProviderRegistry,
    SearchProviderStatus,
    SearchQuery,
    SearchResult,
)


class FakeSearchProvider(SearchProvider):
    def __init__(self, metadata: SearchProviderMetadata, results: tuple[SearchResult, ...] = (), *, delay: float = 0.0, failures: int = 0, health: SearchProviderHealth = SearchProviderHealth.HEALTHY) -> None:
        self.metadata = metadata
        self.results = results
        self.delay = delay
        self.failures = failures
        self.health_value = health
        self.initialized = 0
        self.calls = 0
        self.cancelled = False

    def initialize(self, context: SearchProviderContext) -> None:
        self.initialized += 1

    def shutdown(self) -> None:
        return None

    def search(self, query: SearchQuery, cancellation: SearchCancellationToken) -> tuple[SearchResult, ...]:
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("provider implementation error")
        return () if cancellation.cancelled else self.results

    def health(self) -> SearchProviderStatus:
        return SearchProviderStatus(self.health_value)

    def capabilities(self) -> tuple[SearchCapability, ...]:
        return self.metadata.capabilities

    def priority(self) -> int:
        return self.metadata.priority

    def supports(self, query: SearchQuery) -> bool:
        return set(query.required_capabilities).issubset(self.metadata.capabilities)

    def cancel(self, cancellation: SearchCancellationToken) -> None:
        self.cancelled = True
        cancellation.cancel()


def _metadata(provider_id: str, *capabilities: SearchCapability, priority: int = 0) -> SearchProviderMetadata:
    return SearchProviderMetadata(provider_id, provider_id, capabilities, priority=priority)


def _result(title: str, *, score: float, confidence: float, url: str | None = None) -> SearchResult:
    return SearchResult.create(title, title + " content", "test", score=score, confidence=confidence, url=url)


def test_provider_registration_discovery_lazy_loading_and_dependency_injection():
    context = SearchProviderContext({"marker": "injected"})
    registry = SearchProviderRegistry(context)
    metadata = _metadata("local", SearchCapability.GENERAL, priority=10)
    instances: list[FakeSearchProvider] = []

    def factory(value: SearchProviderContext) -> FakeSearchProvider:
        assert value.require("marker") == "injected"
        provider = FakeSearchProvider(metadata)
        instances.append(provider)
        return provider

    registry.register(metadata, factory)
    assert registry.discover() == (metadata,)
    assert instances == []
    assert registry.get("local").initialized == 1
    registry.set_enabled("local", False)
    assert registry.discover() == ()


def test_provider_selection_priority_health_and_capability_routing():
    registry = SearchProviderRegistry()
    general = _metadata("general", SearchCapability.GENERAL, priority=100)
    docs = _metadata("docs", SearchCapability.DOCUMENTATION, priority=10)
    unhealthy = _metadata("unhealthy", SearchCapability.DOCUMENTATION, priority=200)
    registry.register(general, lambda context: FakeSearchProvider(general, (_result("general", score=1, confidence=1),)))
    registry.register(docs, lambda context: FakeSearchProvider(docs, (_result("docs", score=1, confidence=1),)))
    registry.register(unhealthy, lambda context: FakeSearchProvider(unhealthy, health=SearchProviderHealth.UNHEALTHY))

    response = SearchManager(registry).search(SearchQuery("documentation api"))

    assert [result.title for result in response.results] == ["docs"]
    assert registry.health("unhealthy").health is SearchProviderHealth.UNHEALTHY


def test_parallel_execution_retry_timeout_cancellation_and_partial_failure_handling():
    registry = SearchProviderRegistry()
    first = _metadata("first", SearchCapability.GENERAL)
    second = _metadata("second", SearchCapability.GENERAL)
    slow = _metadata("slow", SearchCapability.GENERAL)
    retrying = FakeSearchProvider(first, (_result("retry", score=1, confidence=1),), failures=1)
    fast = FakeSearchProvider(second, (_result("fast", score=2, confidence=1),), delay=0.08)
    delayed = FakeSearchProvider(slow, (_result("slow", score=1, confidence=1),), delay=0.3)
    registry.register(first, lambda context: retrying)
    registry.register(second, lambda context: fast)
    registry.register(slow, lambda context: delayed)
    manager = SearchManager(registry)

    started = time.monotonic()
    response = manager.search(SearchQuery("hello", retry_count=1, timeout_seconds=0.15))

    assert time.monotonic() - started < 0.25
    assert retrying.calls == 2
    assert {item.title for item in response.results} == {"retry", "fast"}
    assert {item.provider_id for item in response.failures} == {"slow"}

    cancellation = SearchCancellationToken()
    cancellation.cancel()
    cancelled = manager.search(SearchQuery("another", timeout_seconds=0.1), cancellation=cancellation)
    assert cancelled.cancelled is True


def test_aggregation_dedup_ranking_citations_events_cache_and_compatibility_adapter():
    registry = SearchProviderRegistry()
    high = _metadata("high", SearchCapability.GENERAL, priority=10)
    low = _metadata("low", SearchCapability.GENERAL, priority=1)
    duplicate_low = _result("duplicate", score=0.1, confidence=0.1, url="https://example.test/item")
    duplicate_high = _result("duplicate better", score=0.9, confidence=0.9, url="https://example.test/item")
    registry.register(high, lambda context: FakeSearchProvider(high, (duplicate_high, _result("second", score=0.5, confidence=0.5))))
    registry.register(low, lambda context: FakeSearchProvider(low, (duplicate_low,)))
    events: list[EventType] = []
    bus = EventBus()
    bus.subscribe(None, lambda event: events.append(event.event_type))
    manager = SearchManager(registry, event_bus=bus)

    first = manager.search(SearchQuery("same query"))
    second = manager.search(SearchQuery("same query"))

    assert [item.title for item in first.results] == ["duplicate better", "second"]
    assert first.citations[0].url == "https://example.test/item"
    assert second.telemetry.cache_hit is True
    assert events == [
        EventType.SEARCH_STARTED,
        EventType.SEARCH_PROVIDER_STARTED,
        EventType.SEARCH_PROVIDER_STARTED,
        EventType.SEARCH_PROVIDER_COMPLETED,
        EventType.SEARCH_PROVIDER_COMPLETED,
        EventType.SEARCH_COMPLETED,
        EventType.SEARCH_STARTED,
        EventType.SEARCH_COMPLETED,
    ]

    metadata = _metadata("legacy", SearchCapability.GENERAL)
    adapter = CallableSearchProviderAdapter(
        metadata,
        lambda text, limit: (_result("legacy", score=1, confidence=1),),
        lambda: SearchProviderStatus(SearchProviderHealth.HEALTHY),
    )
    assert adapter.search(SearchQuery("legacy"), SearchCancellationToken())[0].title == "legacy"
