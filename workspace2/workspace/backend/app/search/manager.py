"""Provider-neutral orchestration for parallel search operations."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import replace

from ..events.bus import EventBus
from ..events.model import (
    SearchCancelled,
    SearchCompleted,
    SearchPayload,
    SearchProviderCompleted,
    SearchProviderFailed,
    SearchProviderStarted,
    SearchStarted,
)
from .aggregation import SearchFactVerifier, SearchResultAggregator, SourceConsensusVerifier
from .analyzer import QueryAnalyzer
from .cache import InMemorySearchCache, SearchCache
from .models import SearchCitation, SearchFailure, SearchProviderHealth, SearchQuery, SearchResponse, SearchResult, SearchTelemetry
from .provider import SearchCancellationToken
from .registry import SearchProviderRegistry


class SearchManager:
    """Search orchestration that contains no provider-specific implementation."""

    def __init__(
        self,
        registry: SearchProviderRegistry,
        *,
        analyzer: QueryAnalyzer | None = None,
        cache: SearchCache | None = None,
        event_bus: EventBus | None = None,
        cache_ttl_seconds: float = 60.0,
        aggregator: SearchResultAggregator | None = None,
        verifier: SearchFactVerifier | None = None,
    ) -> None:
        self._registry = registry
        self._analyzer = analyzer or QueryAnalyzer()
        self._cache = cache or InMemorySearchCache()
        self._event_bus = event_bus
        self._cache_ttl_seconds = cache_ttl_seconds
        self._aggregator = aggregator or SearchResultAggregator()
        self._verifier = verifier or SourceConsensusVerifier()

    def search(self, query: SearchQuery, *, cancellation: SearchCancellationToken | None = None) -> SearchResponse:
        started = time.monotonic()
        search_id = str(uuid.uuid4())
        cancellation = cancellation or SearchCancellationToken()
        plan = self._analyzer.analyze(query)
        cache_key = self._cache_key(plan.query)
        correlation_id = plan.query.correlation_id or search_id
        self._publish(SearchStarted(source="search_manager", payload=SearchPayload(search_id), correlation_id=correlation_id))
        cached = self._cache.lookup(cache_key)
        if cached is not None:
            response = replace(cached, search_id=search_id, telemetry=replace(cached.telemetry, cache_hit=True))
            self._publish(SearchCompleted(source="search_manager", payload=SearchPayload(search_id, result_count=len(response.results), status="cache"), correlation_id=correlation_id))
            return response
        selected = self._select(plan.query)
        futures = {}
        executor = ThreadPoolExecutor(max_workers=max(1, len(selected)), thread_name_prefix="jarvis-search")
        try:
            for provider_id in selected:
                self._publish(SearchProviderStarted(source="search_manager", payload=SearchPayload(search_id, provider_id), correlation_id=correlation_id))
                futures[executor.submit(self._search_provider, provider_id, plan.query, cancellation)] = provider_id
            done, pending = wait(futures, timeout=max(0.0, plan.query.timeout_seconds))
            failures: list[SearchFailure] = []
            results: list[SearchResult] = []
            for future in done:
                provider_id = futures[future]
                try:
                    provider_results = future.result()
                    results.extend(provider_results)
                    self._publish(SearchProviderCompleted(source="search_manager", payload=SearchPayload(search_id, provider_id, len(provider_results)), correlation_id=correlation_id))
                except Exception:
                    failures.append(SearchFailure(provider_id, "provider unavailable"))
                    self._publish(SearchProviderFailed(source="search_manager", payload=SearchPayload(search_id, provider_id, status="provider unavailable"), correlation_id=correlation_id))
            for future in pending:
                provider_id = futures[future]
                future.cancel()
                failures.append(SearchFailure(provider_id, "provider timeout"))
                self._publish(SearchProviderFailed(source="search_manager", payload=SearchPayload(search_id, provider_id, status="provider timeout"), correlation_id=correlation_id))
            cancelled = cancellation.cancelled
            ranked = self._verifier.verify(self._aggregator.aggregate(tuple(results), limit=plan.query.limit))
            response = SearchResponse(
                search_id, plan.query, ranked, self._aggregator.citations(ranked), tuple(failures), cancelled,
                SearchTelemetry(len(selected), time.monotonic() - started),
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        if cancellation.cancelled:
            self._publish(SearchCancelled(source="search_manager", payload=SearchPayload(search_id, status="cancelled"), correlation_id=correlation_id))
        self._publish(SearchCompleted(source="search_manager", payload=SearchPayload(search_id, result_count=len(response.results)), correlation_id=correlation_id))
        if not response.cancelled:
            self._cache.insert(cache_key, response, self._cache_ttl_seconds)
        return response

    def _select(self, query: SearchQuery) -> tuple[str, ...]:
        selected = []
        for metadata in self._registry.rank(query):
            try:
                provider = self._registry.get(metadata.provider_id)
                if self._registry.health(metadata.provider_id).health is not SearchProviderHealth.UNHEALTHY and provider.supports(query):
                    selected.append(metadata.provider_id)
            except Exception:
                continue
        return tuple(selected)

    def _search_provider(self, provider_id: str, query: SearchQuery, cancellation: SearchCancellationToken) -> tuple[SearchResult, ...]:
        provider = self._registry.get(provider_id)
        attempts = max(1, query.retry_count + 1)
        for attempt in range(attempts):
            if cancellation.cancelled:
                provider.cancel(cancellation)
                return ()
            try:
                return provider.search(query, cancellation)
            except Exception:
                if attempt + 1 == attempts:
                    raise
        return ()

    @staticmethod
    def _cache_key(query: SearchQuery) -> str:
        return "|".join((query.text.lower().strip(), (query.category.value if query.category else ""), str(query.limit), ",".join(capability.value for capability in query.required_capabilities)))

    def _publish(self, event: object) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)  # type: ignore[arg-type]
