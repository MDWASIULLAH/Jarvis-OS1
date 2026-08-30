from __future__ import annotations

from app.brain.decision_engine import DecisionEngine, ModelSelection
from app.brain.intent_router import IntentRouter, RoutingResult
from app.brain.nlu import IntentPrediction
from app.capabilities.builtins import build_builtin_registry
from app.capabilities.contracts import CapabilityContext, CapabilityMetadata
from app.capabilities.registry import CapabilityRegistry
from app.events.bus import EventBus
from app.events.model import EventType


class StubAnalyzer:
    def __init__(self, prediction: IntentPrediction):
        self.prediction = prediction

    def analyze(self, text: str) -> IntentPrediction:
        return self.prediction


def test_router_returns_a_single_intent_with_entities_and_routing_metadata():
    router = IntentRouter(
        StubAnalyzer(IntentPrediction("web.browse", 0.92, "rule", slots={"url": "https://example.com"}))
    )

    result = router.analyze("Read https://example.com")

    assert result.intent == "web.browse"
    assert result.confidence == 0.92
    assert result.entities["url"] == "https://example.com"
    assert result.metadata["source"] == "rule"


def test_low_confidence_and_fallback_predictions_become_unknown_intents():
    low_confidence = IntentRouter(StubAnalyzer(IntentPrediction("task.code", 0.2, "model")))
    fallback = IntentRouter(StubAnalyzer(IntentPrediction("info.factual", 0.0, "fallback")))

    assert low_confidence.analyze("ambiguous request").intent == "unknown"
    assert fallback.analyze("ambiguous request").intent == "unknown"


def test_router_extracts_url_email_quoted_text_and_location_entities():
    router = IntentRouter(StubAnalyzer(IntentPrediction("info.weather", 0.99, "rule")))

    result = router.analyze('Email sam@example.com about "weather report" in New Delhi https://weather.example')

    assert result.entities["email"] == "sam@example.com"
    assert result.entities["quoted_text"] == "weather report"
    assert result.entities["url"] == "https://weather.example"
    assert result.entities["location"] == "New Delhi"


def test_decision_selects_multiple_capabilities_exclusively_from_registry():
    registry = build_builtin_registry()
    engine = DecisionEngine(registry)

    decision = engine.decide(RoutingResult("info.factual", 0.9), has_llm_available=True)

    assert decision.selected_capabilities == ["web_research", "knowledge_apis", "fun_space"]
    assert decision.needs_web is True
    assert decision.needs_tools is True
    assert decision.model is ModelSelection.LOCAL_LLM
    assert [step.capability for step in decision.execution_plan] == decision.selected_capabilities


def test_unknown_intent_does_not_select_capabilities_or_execute_anything():
    registry = build_builtin_registry()
    engine = DecisionEngine(registry)

    decision = engine.decide(RoutingResult("unknown", 0.1))

    assert decision.selected_capabilities == []
    assert decision.execution_plan == []
    assert decision.needs_tools is False
    assert decision.needs_local_llm is True
    assert "defer capability selection" in decision.rationale


def test_decision_selection_reads_registry_metadata_without_loading_capabilities():
    registry = CapabilityRegistry()
    metadata = CapabilityMetadata("metadata_only", "No-load test", supported_intents=("task.code",))

    def factory(context: CapabilityContext):
        raise AssertionError("DecisionEngine must not initialize or execute capabilities")

    registry.register(metadata, factory)
    registry.initialize(CapabilityContext())

    decision = DecisionEngine(registry).decide(RoutingResult("task.code", 0.99))

    assert decision.selected_capabilities == ["metadata_only"]


def test_router_and_decision_publish_typed_events_with_one_correlation_id():
    bus = EventBus()
    observed: list[tuple[EventType, str]] = []
    bus.subscribe(None, lambda event: observed.append((event.event_type, event.correlation_id)))
    router = IntentRouter(StubAnalyzer(IntentPrediction("info.factual", 0.99, "rule")), event_bus=bus)
    engine = DecisionEngine(build_builtin_registry(), event_bus=bus)

    routing = router.analyze("What is JARVIS?", correlation_id="chat-123")
    engine.decide(routing, correlation_id="chat-123")

    assert observed == [
        (EventType.INTENT_RESOLVED, "chat-123"),
        (EventType.DECISION_CREATED, "chat-123"),
    ]


def test_decision_marks_memory_planning_and_confirmation_without_execution():
    registry = build_builtin_registry()
    engine = DecisionEngine(registry)

    memory = engine.decide(RoutingResult("memory.remember", 0.99))
    multi_step = engine.decide(RoutingResult("task.code", 0.99, metadata={"is_multi_step": True}))
    app_open = engine.decide(RoutingResult("action.open_app", 0.99))

    assert memory.needs_memory is True
    assert multi_step.needs_planning is True
    assert app_open.requires_confirmation is True
    assert app_open.execution_plan
