"""Public, analysis-only Reflection Engine API."""

from .manager import ReflectionManager
from .models import (
    FailureCategory, Reflection, ReflectionAttribute, ReflectionKind, ReflectionLesson,
    ReflectionMetric, ReflectionOutcome, ReflectionPattern, ReflectionRecommendation,
    ReflectionReport, ReflectionRequest, ReflectionResult, ReflectionSummary,
)
from .provider import (
    ReflectionProvider, ReflectionProviderContext, ReflectionProviderMetadata,
    ReflectionProviderRegistry, RuleBasedReflectionProvider,
)

__all__ = [
    "FailureCategory", "Reflection", "ReflectionAttribute", "ReflectionKind", "ReflectionLesson",
    "ReflectionManager", "ReflectionMetric", "ReflectionOutcome", "ReflectionPattern",
    "ReflectionProvider", "ReflectionProviderContext", "ReflectionProviderMetadata",
    "ReflectionProviderRegistry", "ReflectionRecommendation", "ReflectionReport",
    "ReflectionRequest", "ReflectionResult", "ReflectionSummary", "RuleBasedReflectionProvider",
]
