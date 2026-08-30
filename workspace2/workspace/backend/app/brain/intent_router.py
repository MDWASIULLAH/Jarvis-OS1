"""Intent Router v2.

This module has one responsibility: turn user text into an inspectable intent
envelope. It never selects, initializes, validates, or executes capabilities.
Resource and execution decisions belong to ``DecisionEngine`` and later
planner/executor phases respectively.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Any, Optional

from ..events.bus import EventBus
from ..events.model import IntentResolved
from .nlu import IntentAnalyzer, IntentPrediction


class IntentType(Enum):
    """Legacy intent enum retained for callers of ``IntentRouter.route``."""

    CHAT = auto()
    QUESTION = auto()
    EXPLAIN = auto()
    CODE = auto()
    DEBUG = auto()
    WORKSPACE = auto()
    GIT = auto()
    OPEN_APP = auto()
    CLOSE_APP = auto()
    FILE = auto()
    FOLDER = auto()
    TERMINAL = auto()
    SYSTEM = auto()
    BROWSER = auto()
    SEARCH = auto()
    WEATHER = auto()
    NEWS = auto()
    MAPS = auto()
    IMAGE_SEARCH = auto()
    IMAGE_GENERATION = auto()
    MUSIC = auto()
    VIDEO = auto()
    TRANSLATE = auto()
    SUMMARIZE = auto()
    ANALYZE = auto()
    OCR = auto()
    CAMERA = auto()
    SCREENSHOT = auto()
    REMEMBER = auto()
    RECALL = auto()
    PLAN = auto()
    MULTISTEP = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class RoutingResult:
    """The only output of the v2 router: intent, entities, confidence, metadata."""

    intent: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_intent(self, intent: str, *, source: str = "router_override") -> "RoutingResult":
        metadata = dict(self.metadata)
        metadata["source"] = source
        return replace(self, intent=intent, metadata=metadata)


@dataclass
class IntentResult:
    """Deprecated compatibility view for callers of the original router API.

    Decision flags remain present only to avoid breaking attribute access. They
    are deliberately not inferred by the router and are always false; callers
    needing resource decisions must use ``DecisionEngine`` with a
    ``RoutingResult``.
    """

    intent: IntentType
    confidence: float
    entities: list[str] = field(default_factory=list)
    needs_llm: bool = False
    needs_web: bool = False
    needs_tools: bool = False
    needs_memory: bool = False
    needs_planner: bool = False
    priority: str = "normal"
    tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntentPattern:
    """Deprecated lexical-pattern shape retained for import compatibility."""

    intent: IntentType
    keywords: tuple[str, ...] = ()
    regex: tuple[str, ...] = ()


_URL = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_QUOTED = re.compile(r"['\"]([^'\"]{1,300})['\"]")
_LOCATION = re.compile(r"\b(?:in|at|for)\s+([A-Za-z][A-Za-z\s\-']{1,60})[?.!]*$", re.IGNORECASE)
_MULTI_STEP = re.compile(r"\b(?:then|after that|and then|next)\b", re.IGNORECASE)

_LEGACY_INTENTS: dict[str, IntentType] = {
    "smalltalk.greeting": IntentType.CHAT,
    "smalltalk.identity": IntentType.CHAT,
    "smalltalk.capabilities": IntentType.CHAT,
    "info.factual": IntentType.QUESTION,
    "info.definition": IntentType.EXPLAIN,
    "info.math": IntentType.QUESTION,
    "info.time": IntentType.QUESTION,
    "info.weather": IntentType.WEATHER,
    "info.news": IntentType.NEWS,
    "info.translate": IntentType.TRANSLATE,
    "info.currency": IntentType.QUESTION,
    "media.image_search": IntentType.IMAGE_SEARCH,
    "media.image_generate": IntentType.IMAGE_GENERATION,
    "media.video_search": IntentType.VIDEO,
    "web.browse": IntentType.BROWSER,
    "action.open_app": IntentType.OPEN_APP,
    "action.web_open": IntentType.BROWSER,
    "action.screenshot": IntentType.SCREENSHOT,
    "action.system_control": IntentType.SYSTEM,
    "memory.remember": IntentType.REMEMBER,
    "memory.recall": IntentType.RECALL,
    "memory.forget": IntentType.RECALL,
    "task.plan": IntentType.PLAN,
    "task.code": IntentType.CODE,
    "vision.analyze": IntentType.OCR,
}


class IntentRouter:
    """Local intent detection, entity extraction, confidence, and routing metadata."""

    def __init__(
        self,
        analyzer: Optional[IntentAnalyzer] = None,
        confidence_threshold: float = 0.55,
        event_bus: EventBus | None = None,
    ):
        self._analyzer = analyzer or IntentAnalyzer()
        self.confidence_threshold = confidence_threshold
        self._event_bus = event_bus

    def analyze(
        self,
        text: str,
        prediction: Optional[IntentPrediction] = None,
        *,
        correlation_id: str | None = None,
    ) -> RoutingResult:
        clean_text = text.strip()
        if not clean_text:
            result = RoutingResult(
                intent="unknown",
                confidence=0.0,
                metadata={"source": "empty", "candidate_intents": [], "is_multi_step": False},
            )
            self._publish(result, correlation_id)
            return result

        prediction = prediction or self._analyzer.analyze(clean_text)
        intent = prediction.intent
        is_unknown = prediction.source == "fallback" or (
            prediction.source == "model" and prediction.confidence < self.confidence_threshold
        )
        if is_unknown:
            intent = "unknown"

        entities = self._extract_entities(clean_text, prediction.slots)
        candidates = [label for label, _ in sorted(prediction.scores.items(), key=lambda item: item[1], reverse=True)]
        if prediction.intent not in candidates:
            candidates.insert(0, prediction.intent)
        result = RoutingResult(
            intent=intent,
            confidence=prediction.confidence,
            entities=entities,
            metadata={
                "source": prediction.source,
                "slots": dict(prediction.slots),
                "candidate_intents": candidates[:3],
                "is_multi_step": bool(_MULTI_STEP.search(clean_text)),
            },
        )
        self._publish(result, correlation_id)
        return result

    def route(self, text: str) -> IntentResult:
        """Return the original shape without leaking resource decisions into routing."""
        result = self.analyze(text)
        entity_values = [str(value) for value in result.entities.values() if isinstance(value, (str, int, float))]
        return IntentResult(
            intent=_LEGACY_INTENTS.get(result.intent, IntentType.UNKNOWN),
            confidence=result.confidence,
            entities=entity_values,
            metadata={"canonical_intent": result.intent, **result.metadata, "entities": result.entities},
        )

    def _publish(self, result: RoutingResult, correlation_id: str | None) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(
                IntentResolved(
                    source="intent_router",
                    payload=result,
                    correlation_id=correlation_id or "router:" + result.intent,
                )
            )

    @staticmethod
    def _extract_entities(text: str, slots: dict[str, Any]) -> dict[str, Any]:
        entities = {key: value for key, value in slots.items() if value not in (None, "", [], {})}
        urls = _URL.findall(text)
        if urls:
            entities.setdefault("url", urls[0])
            entities["urls"] = urls
        emails = _EMAIL.findall(text)
        if emails:
            entities.setdefault("email", emails[0])
        quoted = _QUOTED.findall(text)
        if quoted:
            entities.setdefault("quoted_text", quoted[0])
        location = _LOCATION.search(_URL.sub("", text).strip())
        if location:
            entities.setdefault("location", location.group(1).strip())
        return entities
