"""Public, recommendation-only Evolution Engine API."""

from .manager import EvolutionManager
from .models import (
    EvolutionHistory, EvolutionProposal, EvolutionRecommendation, EvolutionReport,
    EvolutionRequest, EvolutionResult, ImpactAssessment, ImprovementMetric,
    ImprovementOpportunity, OptimizationPlan, OptimizationTarget, RiskAssessment, RiskLevel,
)
from .provider import EvolutionProvider, EvolutionProviderContext, EvolutionProviderMetadata, EvolutionProviderRegistry, RuleBasedEvolutionProvider

__all__ = ["EvolutionHistory", "EvolutionManager", "EvolutionProposal", "EvolutionProvider", "EvolutionProviderContext", "EvolutionProviderMetadata", "EvolutionProviderRegistry", "EvolutionRecommendation", "EvolutionReport", "EvolutionRequest", "EvolutionResult", "ImpactAssessment", "ImprovementMetric", "ImprovementOpportunity", "OptimizationPlan", "OptimizationTarget", "RiskAssessment", "RiskLevel", "RuleBasedEvolutionProvider"]
