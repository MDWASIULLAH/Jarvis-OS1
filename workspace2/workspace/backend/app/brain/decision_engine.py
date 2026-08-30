"""Non-executing, registry-driven decision engine.

The engine consumes ``RoutingResult`` values and capability metadata. It only
selects possible capabilities and records an execution plan for a future
planner/executor; it never imports, initializes, validates, or executes a
capability itself.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..capabilities.registry import CapabilityRegistry
from ..events.bus import EventBus
from ..events.model import DecisionCreated
from .intent_router import RoutingResult


class ModelSelection(str, Enum):
    NONE = "none"
    LOCAL_LLM = "local_llm"
    CLOUD_LLM = "cloud_llm"
    LOCAL_REASONING = "local_reasoning"


class DecisionPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class FallbackStrategy(str, Enum):
    LOCAL_REASONING = "local_reasoning"
    DECLINE = "decline"
    RETRY = "retry"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0


@dataclass(frozen=True)
class DecisionTelemetry:
    correlation_id: str | None = None
    decision_source: str = "decision_engine"


@dataclass(frozen=True)
class DecisionAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class DecisionMetadata:
    attributes: tuple[DecisionAttribute, ...] = ()


@dataclass(frozen=True)
class CapabilityPlanStep:
    """A proposed operation target; not an instruction to execute it."""

    capability: str
    reason: str
    entities: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"capability": self.capability, "reason": self.reason, "entities": dict(self.entities)}


@dataclass
class Decision:
    """Structured, non-executing resource decision for one routed request."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    routing: RoutingResult | None = None
    intent: str = "unknown"
    confidence: float = 0.0
    selected_capabilities: list[str] = field(default_factory=list)
    execution_plan: list[CapabilityPlanStep] = field(default_factory=list)
    priority: DecisionPriority = DecisionPriority.NORMAL
    estimated_cost: float | None = None
    requires_confirmation: bool = False
    requires_memory: bool = False
    requires_planner: bool = False
    requires_streaming: bool = False
    requires_parallel_execution: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_seconds: float | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    fallback_strategy: FallbackStrategy = FallbackStrategy.LOCAL_REASONING
    telemetry: DecisionTelemetry = field(default_factory=DecisionTelemetry)
    metadata: DecisionMetadata = field(default_factory=DecisionMetadata)
    needs_web: bool = False
    needs_local_llm: bool = False
    needs_cloud_llm: bool = False
    needs_tools: bool = False
    model: ModelSelection = ModelSelection.NONE
    rationale: str = ""
    preferred_provider: str = "local"

    # Compatibility properties for the existing v1 response payload.
    @property
    def tools_needed(self) -> list[str]:
        return list(self.selected_capabilities)

    @property
    def connectors_needed(self) -> list[str]:
        return []

    @property
    def needs_internet(self) -> bool:
        return self.needs_web

    @property
    def needs_planning(self) -> bool:
        return self.requires_planner

    @property
    def needs_memory(self) -> bool:
        return self.requires_memory

    @property
    def needs_memory_update(self) -> bool:
        return self.needs_memory

    @property
    def needs_web_search(self) -> bool:
        return "web_research" in self.selected_capabilities or "knowledge_apis" in self.selected_capabilities

    @property
    def needs_code_exec(self) -> bool:
        return "code_execution" in self.selected_capabilities

    @property
    def needs_ocr(self) -> bool:
        return "vision_ocr" in self.selected_capabilities

    @property
    def needs_vision(self) -> bool:
        return self.needs_ocr

    @property
    def needs_image_gen(self) -> bool:
        return "image_pipeline" in self.selected_capabilities and self.intent == "media.image_generate"

    @property
    def needs_browser(self) -> bool:
        return "web_research" in self.selected_capabilities

    @property
    def needs_desktop(self) -> bool:
        return "desktop_automation" in self.selected_capabilities or "app_launcher" in self.selected_capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "selected_capabilities": self.selected_capabilities,
            "execution_plan": [step.to_dict() for step in self.execution_plan],
            "needs_planning": self.needs_planning,
            "needs_memory": self.needs_memory,
            "priority": self.priority.value,
            "estimated_cost": self.estimated_cost,
            "requires_confirmation": self.requires_confirmation,
            "requires_memory": self.requires_memory,
            "requires_planner": self.requires_planner,
            "requires_streaming": self.requires_streaming,
            "requires_parallel_execution": self.requires_parallel_execution,
            "risk_level": self.risk_level.value,
            "timeout_seconds": self.timeout_seconds,
            "retry_policy": {"max_attempts": self.retry_policy.max_attempts, "backoff_seconds": self.retry_policy.backoff_seconds},
            "fallback_strategy": self.fallback_strategy.value,
            "telemetry": {"correlation_id": self.telemetry.correlation_id, "decision_source": self.telemetry.decision_source},
            "metadata": {"attributes": [{"key": item.key, "value": item.value} for item in self.metadata.attributes]},
            "needs_web": self.needs_web,
            "needs_local_llm": self.needs_local_llm,
            "needs_cloud_llm": self.needs_cloud_llm,
            "needs_tools": self.needs_tools,
            "model": self.model.value,
            "tools_needed": self.tools_needed,
            "connectors_needed": self.connectors_needed,
            "needs_internet": self.needs_internet,
            "needs_ocr": self.needs_ocr,
            "needs_vision": self.needs_vision,
            "needs_image_gen": self.needs_image_gen,
            "needs_browser": self.needs_browser,
            "needs_desktop": self.needs_desktop,
            "needs_memory_update": self.needs_memory_update,
            "needs_web_search": self.needs_web_search,
            "needs_code_exec": self.needs_code_exec,
            "rationale": self.rationale,
            "preferred_provider": self.preferred_provider,
        }


class DecisionEngine:
    """Select capabilities and execution requirements without executing work."""

    _CONFIRMATION_PERMISSIONS = frozenset(
        {"app_open", "desktop_control", "email_send", "file_write", "system_control", "smart_home_control"}
    )
    _DETERMINISTIC_INTENTS = frozenset({"info.math", "info.time", "memory.remember", "memory.recall", "memory.forget"})

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        confidence_threshold: float = 0.55,
        event_bus: EventBus | None = None,
    ):
        self._registry = registry
        self.confidence_threshold = confidence_threshold
        self._event_bus = event_bus
        self._decision_history: list[dict[str, Any]] = []

    def decide(
        self,
        routing: RoutingResult | str,
        *,
        registry: Optional[CapabilityRegistry] = None,
        has_attachments: bool = False,
        has_llm_available: bool = False,
        correlation_id: str | None = None,
    ) -> Decision:
        """Produce a decision only; no selected capability is loaded or run."""
        if isinstance(routing, str):
            routing = RoutingResult(routing, 1.0, metadata={"source": "legacy_adapter", "is_multi_step": False})
        active_registry = registry or self._registry
        if active_registry is None:
            raise RuntimeError("DecisionEngine requires a CapabilityRegistry.")
        self._registry = active_registry

        low_confidence = routing.intent == "unknown" or routing.confidence < self.confidence_threshold
        selected = [] if low_confidence else [item.name for item in active_registry.rank(intent=routing.intent)]
        if has_attachments and "vision_ocr" not in selected:
            selected.extend(item.name for item in active_registry.rank(intent="vision.analyze"))
        selected = list(dict.fromkeys(selected))
        metadata = [active_registry.metadata(name) for name in selected]

        needs_memory = routing.intent.startswith("memory.")
        needs_planning = routing.intent == "task.plan" or bool(routing.metadata.get("is_multi_step"))
        needs_web = any("network" in item.permissions for item in metadata)
        requires_confirmation = any(
            self._CONFIRMATION_PERMISSIONS.intersection(item.permissions) for item in metadata
        )
        needs_tools = bool(selected)
        needs_local_llm = (
            not low_confidence
            and routing.intent not in self._DETERMINISTIC_INTENTS
            and routing.intent not in {"smalltalk.greeting", "smalltalk.thanks", "smalltalk.bye"}
        ) or low_confidence
        model = ModelSelection.LOCAL_LLM if needs_local_llm and has_llm_available else (
            ModelSelection.LOCAL_REASONING if needs_local_llm else ModelSelection.NONE
        )

        reason = "low-confidence or unknown intent; defer capability selection" if low_confidence else (
            "selected capabilities exclusively from registry metadata" if selected else "no registered capability supports this intent"
        )
        decision = Decision(
            intent=routing.intent,
            confidence=routing.confidence,
            routing=routing,
            selected_capabilities=selected,
            execution_plan=[
                CapabilityPlanStep(
                    item.name,
                    f"supports intent '{routing.intent}'",
                    tuple((key, str(value)) for key, value in sorted(routing.entities.items())),
                )
                for item in metadata
            ],
            requires_planner=needs_planning,
            requires_memory=needs_memory,
            requires_confirmation=requires_confirmation,
            risk_level=RiskLevel.MODERATE if requires_confirmation else RiskLevel.LOW,
            telemetry=DecisionTelemetry(correlation_id=correlation_id),
            needs_web=needs_web,
            needs_local_llm=needs_local_llm,
            needs_tools=needs_tools,
            model=model,
            rationale=reason,
        )
        self._decision_history.append(decision.to_dict())
        if len(self._decision_history) > 100:
            self._decision_history = self._decision_history[-100:]
        if self._event_bus is not None:
            self._event_bus.publish(
                DecisionCreated(
                    source="decision_engine",
                    payload=decision,
                    correlation_id=correlation_id or decision.decision_id,
                )
            )
        return decision

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._decision_history[-max(1, limit):]

    def status(self) -> dict[str, Any]:
        registered = len(self._registry.registered_names()) if self._registry is not None else 0
        return {
            # Legacy status keys remain available while their values now come
            # from the registry rather than an independent tool catalogue.
            "intents_registered": registered,
            "decisions_made": len(self._decision_history),
            "available_tools": registered,
            "available_connectors": 0,
            "registry_configured": self._registry is not None,
            "confidence_threshold": self.confidence_threshold,
        }
