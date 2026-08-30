"""Search Intelligence public contracts and manager."""

from .adapters import CallableSearchProviderAdapter
from .aggregation import SearchFactVerifier, SearchResultAggregator, SourceConsensusVerifier
from .analyzer import QueryAnalyzer, SearchPlan
from .cache import InMemorySearchCache, SearchCache
from .manager import SearchManager
from .models import (
    SearchAttribute, SearchCapability, SearchCategory, SearchCitation, SearchFailure, SearchProviderHealth,
    SearchProviderMetadata, SearchProviderStatus, SearchQuery, SearchResponse, SearchResult, SearchTelemetry,
)
from .provider import SearchCancellationToken, SearchProvider, SearchProviderContext
from .registry import SearchProviderRegistry

__all__ = [
    "CallableSearchProviderAdapter", "InMemorySearchCache", "QueryAnalyzer", "SearchAttribute", "SearchCache", "SearchFactVerifier",
    "SearchCancellationToken", "SearchCapability", "SearchCategory", "SearchCitation", "SearchFailure", "SearchManager",
    "SearchPlan", "SearchProvider", "SearchProviderContext", "SearchProviderHealth", "SearchProviderMetadata",
    "SearchProviderRegistry", "SearchProviderStatus", "SearchQuery", "SearchResponse", "SearchResult", "SearchResultAggregator", "SearchTelemetry", "SourceConsensusVerifier",
]
