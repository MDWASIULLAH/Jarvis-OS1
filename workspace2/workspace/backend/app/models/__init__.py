"""Model Manager public API."""

from .adapters import LegacyLLMProviderAdapter
from .contracts import (
    GenerationMetrics,
    ModelAttribute,
    ModelCapability,
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
from .manager import ModelManager, ModelProviderUnavailable
from .registry import ModelProviderRegistry

__all__ = [
    "GenerationMetrics", "LegacyLLMProviderAdapter", "ModelAttribute", "ModelCapability", "ModelManager",
    "ModelProvider", "ModelProviderContext", "ModelProviderRegistry", "ModelProviderUnavailable", "ModelRequest",
    "ModelResponse", "ModelResponseChunk", "ModelTask", "ProviderHealth", "ProviderHealthStatus", "ProviderKind",
    "ProviderMetadata", "StreamingModelResponse", "TokenUsage",
]
