"""Provider-independent normalization, aggregation, and verification hooks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace

from .models import SearchCitation, SearchResult


class SearchFactVerifier(ABC):
    """Injectable verification boundary for future fact-checking services."""

    @abstractmethod
    def verify(self, results: tuple[SearchResult, ...]) -> tuple[SearchResult, ...]: ...


class SourceConsensusVerifier(SearchFactVerifier):
    """Conservative in-process confidence adjustment based on source diversity."""

    def verify(self, results: tuple[SearchResult, ...]) -> tuple[SearchResult, ...]:
        source_counts: dict[str, int] = {}
        for result in results:
            source_counts[result.source] = source_counts.get(result.source, 0) + 1
        return tuple(
            replace(result, confidence=min(1.0, max(0.0, result.confidence) + (0.05 if source_counts[result.source] > 1 else 0.0)))
            for result in results
        )


class SearchResultAggregator:
    def aggregate(self, results: tuple[SearchResult, ...], *, limit: int) -> tuple[SearchResult, ...]:
        unique: dict[str, SearchResult] = {}
        for original in results:
            result = self._normalize(original)
            key = result.url or f"{result.title}:{result.content}"
            existing = unique.get(key)
            if existing is None or (result.score + result.confidence) > (existing.score + existing.confidence):
                unique[key] = result
        ranked = sorted(unique.values(), key=lambda item: (-(item.score + item.confidence), item.title.lower()))
        return tuple(ranked[:max(0, limit)])

    @staticmethod
    def citations(results: tuple[SearchResult, ...]) -> tuple[SearchCitation, ...]:
        citations = []
        for result in results:
            citations.extend(result.citations or (SearchCitation(result.source, result.title, result.url),))
        unique = {(item.source, item.title, item.url): item for item in citations}
        return tuple(unique[key] for key in sorted(unique))

    @staticmethod
    def _normalize(result: SearchResult) -> SearchResult:
        return replace(
            result,
            title=" ".join(result.title.split()),
            content=" ".join(result.content.split()),
            source=result.source.strip().lower(),
            url=result.url.strip().lower() if result.url else None,
            confidence=min(1.0, max(0.0, result.confidence)),
        )
