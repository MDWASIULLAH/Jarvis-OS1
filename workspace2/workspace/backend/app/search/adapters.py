"""Compatibility adapter for existing callable-based search implementations."""

from __future__ import annotations

from collections.abc import Callable

from .models import SearchCapability, SearchProviderMetadata, SearchProviderStatus, SearchQuery, SearchResult
from .provider import SearchCancellationToken, SearchProvider, SearchProviderContext

LegacySearchCallable = Callable[[str, int], tuple[SearchResult, ...]]


class CallableSearchProviderAdapter(SearchProvider):
    """Wraps an existing search function without coupling SearchManager to it."""

    def __init__(
        self,
        metadata: SearchProviderMetadata,
        search_callable: LegacySearchCallable,
        health_callable: Callable[[], SearchProviderStatus],
    ) -> None:
        self._metadata = metadata
        self._search_callable = search_callable
        self._health_callable = health_callable

    def initialize(self, context: SearchProviderContext) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def search(self, query: SearchQuery, cancellation: SearchCancellationToken) -> tuple[SearchResult, ...]:
        return () if cancellation.cancelled else self._search_callable(query.text, query.limit)

    def health(self) -> SearchProviderStatus:
        return self._health_callable()

    def capabilities(self) -> tuple[SearchCapability, ...]:
        return self._metadata.capabilities

    def priority(self) -> int:
        return self._metadata.priority

    def supports(self, query: SearchQuery) -> bool:
        return set(query.required_capabilities).issubset(self._metadata.capabilities)

    def cancel(self, cancellation: SearchCancellationToken) -> None:
        cancellation.cancel()
