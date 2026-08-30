"""
brain/decision_engine.py

Dedicated Decision Engine.

The Decision Engine sits between intent classification and tool execution.
It decides *which* model, tool, connector, and API to use based on the
request context, available capabilities, and past performance.

It is NOT the LLM -- the LLM is one of its tools. The engine evaluates
the request and makes routing decisions deterministically before any
generative model is called.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ModelSelection(str, Enum):
    NONE = "none"
    LOCAL_LLM = "local_llm"
    CLOUD_LLM = "cloud_llm"
    LOCAL_REASONING = "local_reasoning"


class ToolCategory(str, Enum):
    KNOWLEDGE = "knowledge"
    BROWSER = "browser"
    OCR = "ocr"
    VISION = "vision"
    IMAGE_GEN = "image_generation"
    WEB_SEARCH = "web_search"
    LOCAL_MODEL = "local_model"
    PYTHON = "python"
    GITHUB = "github"
    EMAIL = "email"
    CALENDAR = "calendar"
    SYSTEM = "system"
    AUTOMATION = "automation"


@dataclass
class Decision:
    """The engine's decision for a single request."""
    model: ModelSelection = ModelSelection.NONE
    tools_needed: list[ToolCategory] = field(default_factory=list)
    connectors_needed: list[str] = field(default_factory=list)
    needs_internet: bool = False
    needs_ocr: bool = False
    needs_vision: bool = False
    needs_image_gen: bool = False
    needs_browser: bool = False
    needs_desktop: bool = False
    needs_memory_update: bool = False
    needs_web_search: bool = False
    needs_code_exec: bool = False
    confidence: float = 1.0
    rationale: str = ""
    preferred_provider: str = "local"

    def to_dict(self) -> dict:
        return {
            "model": self.model.value,
            "tools_needed": [t.value for t in self.tools_needed],
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
            "confidence": round(self.confidence, 4),
            "rationale": self.rationale,
            "preferred_provider": self.preferred_provider,
        }


class DecisionEngine:
    """Evaluates every request and decides what resources are needed.

    This is a deterministic, inspectable router. It never sends request text
    to a cloud classifier -- all decisions are based on local intent analysis,
    keyword matches, and available capability state.
    """

    INTENT_TO_DECISION: dict[str, Decision] = {}
    for _intent, _decision in {
        "info.factual": Decision(
            model=ModelSelection.LOCAL_LLM,
            tools_needed=[ToolCategory.KNOWLEDGE, ToolCategory.WEB_SEARCH],
            needs_internet=True, needs_web_search=True, needs_memory_update=True,
            rationale="Factual queries need verified sources and search.",
        ),
        "info.definition": Decision(
            model=ModelSelection.LOCAL_REASONING,
            tools_needed=[ToolCategory.KNOWLEDGE],
            needs_internet=False,
            rationale="Definitions can be answered from local dictionary or cached knowledge.",
        ),
        "info.math": Decision(
            model=ModelSelection.NONE,
            tools_needed=[ToolCategory.PYTHON],
            needs_internet=False, needs_code_exec=True,
            rationale="Math is evaluated deterministically, no LLM needed.",
        ),
        "info.time": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_internet=False,
            rationale="Clock reads are local and deterministic.",
        ),
        "info.weather": Decision(
            model=ModelSelection.LOCAL_REASONING,
            tools_needed=[],
            connectors_needed=["openweather"],
            needs_internet=True,
            rationale="Weather data comes from API, composed by local reasoning.",
        ),
        "info.news": Decision(
            model=ModelSelection.LOCAL_LLM,
            tools_needed=[],
            connectors_needed=["newsapi"],
            needs_internet=True,
            rationale="News requires internet access to providers.",
        ),
        "info.translate": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_internet=True,
            rationale="Translation uses dedicated API, no LLM required.",
        ),
        "info.currency": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_internet=True,
            rationale="Currency conversion uses dedicated API.",
        ),
        "media.image_search": Decision(
            model=ModelSelection.NONE,
            tools_needed=[ToolCategory.WEB_SEARCH],
            needs_internet=True, needs_memory_update=True,
            rationale="Image search fetches from web sources and caches locally.",
        ),
        "media.image_generate": Decision(
            model=ModelSelection.NONE,
            tools_needed=[ToolCategory.IMAGE_GEN],
            needs_internet=True, needs_image_gen=True,
            connectors_needed=["image_api"],
            rationale="Image generation calls the configured image API.",
        ),
        "media.video_search": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            connectors_needed=["youtube"],
            needs_internet=True,
            rationale="Video search uses YouTube API when configured.",
        ),
        "web.browse": Decision(
            model=ModelSelection.LOCAL_LLM,
            tools_needed=[ToolCategory.BROWSER],
            needs_internet=True, needs_browser=True,
            rationale="Web browsing requires fetching and summarizing pages.",
        ),
        "action.open_app": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_desktop=True,
            rationale="Opening apps is a local desktop action, no model needed.",
        ),
        "action.web_open": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_desktop=True, needs_browser=True,
            rationale="Opening URLs is a local desktop action.",
        ),
        "action.screenshot": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_desktop=True,
            rationale="Screenshot requires desktop automation.",
        ),
        "action.system_control": Decision(
            model=ModelSelection.NONE,
            tools_needed=[ToolCategory.SYSTEM],
            needs_desktop=True,
            rationale="System control reads local metrics, no model needed.",
        ),
        "memory.remember": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_memory_update=True,
            rationale="Memory write is local, encrypted, and deterministic.",
        ),
        "memory.recall": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_internet=False,
            rationale="Memory recall searches local encrypted store.",
        ),
        "memory.forget": Decision(
            model=ModelSelection.NONE,
            tools_needed=[],
            needs_internet=False,
            rationale="Memory deletion requires explicit confirmation but no model.",
        ),
        "task.plan": Decision(
            model=ModelSelection.LOCAL_LLM,
            tools_needed=[ToolCategory.KNOWLEDGE],
            needs_memory_update=True,
            rationale="Planning benefits from LLM reasoning and memory context.",
        ),
        "task.code": Decision(
            model=ModelSelection.LOCAL_LLM,
            tools_needed=[ToolCategory.PYTHON, ToolCategory.GITHUB],
            needs_code_exec=True,
            rationale="Code tasks need the coding agent, execution sandbox, and optionally GitHub.",
        ),
        "vision.analyze": Decision(
            model=ModelSelection.LOCAL_LLM,
            tools_needed=[ToolCategory.VISION, ToolCategory.OCR],
            needs_vision=True, needs_ocr=True,
            rationale="Vision analysis requires OCR extraction and optionally a vision-capable local model.",
        ),
    }.items():
        INTENT_TO_DECISION[_intent] = _decision

    _DEFAULT_DECISION = Decision(
        model=ModelSelection.LOCAL_LLM,
        tools_needed=[ToolCategory.KNOWLEDGE, ToolCategory.WEB_SEARCH],
        needs_internet=True, needs_web_search=True, needs_memory_update=True,
        rationale="Default: multi-source knowledge search with local model.",
    )

    def __init__(self):
        self._tool_availability: dict[str, bool] = {}
        self._connector_status: dict[str, bool] = {}
        self._decision_history: list[dict] = []

    def set_tool_availability(self, tool_states: dict[str, bool]) -> None:
        self._tool_availability = tool_states

    def set_connector_status(self, connector_states: dict[str, bool]) -> None:
        self._connector_status = connector_states

    def decide(
        self,
        intent: str,
        text: str = "",
        has_attachments: bool = False,
        has_llm_available: bool = False,
    ) -> Decision:
        base = self.INTENT_TO_DECISION.get(intent, self._DEFAULT_DECISION)
        decision = Decision(
            model=base.model,
            tools_needed=list(base.tools_needed),
            connectors_needed=list(base.connectors_needed),
            needs_internet=base.needs_internet,
            needs_ocr=base.needs_ocr,
            needs_vision=base.needs_vision,
            needs_image_gen=base.needs_image_gen,
            needs_browser=base.needs_browser,
            needs_desktop=base.needs_desktop,
            needs_memory_update=base.needs_memory_update,
            needs_web_search=base.needs_web_search,
            needs_code_exec=base.needs_code_exec,
            confidence=base.confidence,
            rationale=base.rationale,
        )

        if has_attachments:
            decision.needs_ocr = True
            decision.needs_vision = True
            if ToolCategory.OCR not in decision.tools_needed:
                decision.tools_needed.append(ToolCategory.OCR)
            if ToolCategory.VISION not in decision.tools_needed:
                decision.tools_needed.append(ToolCategory.VISION)

        if not has_llm_available and decision.model == ModelSelection.LOCAL_LLM:
            decision.model = ModelSelection.LOCAL_REASONING
            decision.rationale += " (fallback: no LLM available, using local reasoning)"

        self._apply_tool_overrides(decision, text)

        self._decision_history.append(decision.to_dict())
        if len(self._decision_history) > 100:
            self._decision_history = self._decision_history[-100:]

        return decision

    def _apply_tool_overrides(self, decision: Decision, text: str) -> None:
        lowered = text.lower()

        code_patterns = [
            r"\b(code|program|script|function|algorithm|debug|refactor|compile|syntax)\b",
            r"\b(write|create|generate|build|fix|repair).*(?:code|script|program|app|function)\b",
            r"```python|```javascript|```html|```css|```bash",
        ]
        for pat in code_patterns:
            if re.search(pat, lowered):
                if ToolCategory.PYTHON not in decision.tools_needed:
                    decision.tools_needed.append(ToolCategory.PYTHON)
                decision.needs_code_exec = True
                if decision.model == ModelSelection.NONE:
                    decision.model = ModelSelection.LOCAL_LLM
                break

        email_patterns = [
            r"\b(send|compose|draft|write)\s+(?:an?\s+)?(?:email|mail|message)\b",
            r"\bemail\s+(?:to|for|about)\b",
        ]
        for pat in email_patterns:
            if re.search(pat, lowered):
                if "gmail" not in decision.connectors_needed:
                    decision.connectors_needed.append("gmail")
                if ToolCategory.EMAIL not in decision.tools_needed:
                    decision.tools_needed.append(ToolCategory.EMAIL)
                decision.needs_internet = True
                break

        calendar_patterns = [
            r"\b(schedule|create|add|set)\s+(?:a\s+)?(?:calendar\s+)?(?:event|meeting|appointment|reminder)\b",
        ]
        for pat in calendar_patterns:
            if re.search(pat, lowered):
                if "google_calendar" not in decision.connectors_needed:
                    decision.connectors_needed.append("google_calendar")
                if ToolCategory.CALENDAR not in decision.tools_needed:
                    decision.tools_needed.append(ToolCategory.CALENDAR)
                break

        automation_patterns = [
            r"\b(click|type|drag|press|scroll|move\s+mouse)\b",
            r"\b(open|start|launch|close)\s+(?:chrome|firefox|browser|terminal|notepad|calculator)\b",
        ]
        for pat in automation_patterns:
            if re.search(pat, lowered):
                if ToolCategory.AUTOMATION not in decision.tools_needed:
                    decision.tools_needed.append(ToolCategory.AUTOMATION)
                decision.needs_desktop = True
                break

        url_pattern = r"https?://[^\s]+"
        if re.search(url_pattern, lowered):
            if ToolCategory.BROWSER not in decision.tools_needed:
                decision.tools_needed.append(ToolCategory.BROWSER)
            decision.needs_browser = True
            decision.needs_internet = True

    def get_history(self, limit: int = 20) -> list[dict]:
        return self._decision_history[-limit:]

    def status(self) -> dict:
        return {
            "intents_registered": len(self.INTENT_TO_DECISION),
            "decisions_made": len(self._decision_history),
            "available_tools": sum(1 for v in self._tool_availability.values() if v),
            "available_connectors": sum(1 for v in self._connector_status.values() if v),
        }
