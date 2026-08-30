"""Query classification and provider-capability planning."""

from __future__ import annotations

from dataclasses import dataclass

from .models import SearchCapability, SearchCategory, SearchQuery


@dataclass(frozen=True)
class SearchPlan:
    query: SearchQuery
    required_capabilities: tuple[SearchCapability, ...]


class QueryAnalyzer:
    def analyze(self, query: SearchQuery) -> SearchPlan:
        category = query.category or self._classify(query.text)
        capabilities = tuple(dict.fromkeys((*query.required_capabilities, self._capability(category))))
        normalized = SearchQuery(
            text=" ".join(query.text.split()), category=category, limit=query.limit, timeout_seconds=query.timeout_seconds,
            retry_count=query.retry_count, preferred_provider_ids=query.preferred_provider_ids,
            required_capabilities=capabilities, correlation_id=query.correlation_id, metadata=query.metadata,
        )
        return SearchPlan(normalized, capabilities)

    @staticmethod
    def _classify(text: str) -> SearchCategory:
        value = text.lower()
        if any(item in value for item in ("python", "error", "code", "function", "debug")):
            return SearchCategory.PROGRAMMING
        if any(item in value for item in ("news", "today", "latest", "current")):
            return SearchCategory.CURRENT_EVENTS
        if any(item in value for item in ("docs", "documentation", "api reference")):
            return SearchCategory.DOCUMENTATION
        if any(item in value for item in ("package", "pip", "npm")):
            return SearchCategory.PACKAGES
        if any(item in value for item in ("dataset", "csv", "benchmark")):
            return SearchCategory.DATASETS
        if any(item in value for item in ("image", "photo")):
            return SearchCategory.IMAGES
        if any(item in value for item in ("video", "youtube")):
            return SearchCategory.VIDEOS
        return SearchCategory.GENERAL

    @staticmethod
    def _capability(category: SearchCategory) -> SearchCapability:
        return {
            SearchCategory.PROGRAMMING: SearchCapability.DOCUMENTATION,
            SearchCategory.DOCUMENTATION: SearchCapability.DOCUMENTATION,
            SearchCategory.CURRENT_EVENTS: SearchCapability.NEWS,
            SearchCategory.IMAGES: SearchCapability.IMAGES,
            SearchCategory.VIDEOS: SearchCapability.VIDEOS,
            SearchCategory.PACKAGES: SearchCapability.PACKAGES,
            SearchCategory.FILES: SearchCapability.FILES,
        }.get(category, SearchCapability.GENERAL)
