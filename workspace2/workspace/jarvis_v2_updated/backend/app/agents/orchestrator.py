"""Privacy-preserving multi-agent planning and execution.

Agents are roles with narrow system instructions, not independent processes
with unrestricted computer access. The central permission gate remains the
only path from a plan to a real-world action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..brain.llm_interface import LLMBackend, ModelRouter
from ..memory.memory_store import MemorySystem
from ..memory.semantic_search import SemanticIndex
from ..observability.audit import AuditLog
from ..tasks.store import TaskStatus, TaskStore


class AgentName(str, Enum):
    CODING = "coding"
    RESEARCH = "research"
    MEMORY = "memory"
    PLANNING = "planning"
    BROWSER = "browser"
    DOCUMENT = "document"
    VISION = "vision"
    VOICE = "voice"
    EMAIL = "email"
    CALENDAR = "calendar"
    SECURITY = "security"
    AUTOMATION = "automation"
    FILES = "files"
    ANALYTICS = "analytics"


_AGENT_INSTRUCTIONS = {
    AgentName.CODING: "Produce safe, testable code guidance. Never claim commands ran unless they did.",
    AgentName.RESEARCH: "Separate known facts from assumptions and cite sources when a web source is actually used.",
    AgentName.MEMORY: "Use only the supplied local memory context; never invent personal preferences.",
    AgentName.PLANNING: "Break work into reversible, dependency-aware steps and call out confirmations needed.",
    AgentName.BROWSER: "Plan browser actions conservatively. Credentials, purchases, and OTPs require user control.",
    AgentName.DOCUMENT: "Create a clear outline suited to the requested document format.",
    AgentName.VISION: "Describe only visible evidence and flag uncertain visual inferences.",
    AgentName.VOICE: "Optimize for short, natural spoken responses; do not imply microphone access without it.",
    AgentName.EMAIL: "Draft only. Sending email always needs explicit confirmation.",
    AgentName.CALENDAR: "Propose event details. Creating a calendar event requires explicit confirmation.",
    AgentName.SECURITY: "Identify privacy, permission, and credential risks before recommending any action.",
    AgentName.AUTOMATION: "Prefer a preview and explicit confirmation for desktop or device control.",
    AgentName.FILES: "Never delete or overwrite files without an explicit, reviewable confirmation.",
    AgentName.ANALYTICS: "Explain local metrics and limitations without collecting hidden telemetry.",
}


_KEYWORDS: tuple[tuple[AgentName, tuple[str, ...]], ...] = (
    (AgentName.CODING, ("code", "debug", "test", "repository", "github", "pull request", "program")),
    (AgentName.RESEARCH, ("research", "compare", "find out", "news", "source", "search")),
    (AgentName.MEMORY, ("remember", "recall", "preference", "memory", "forget")),
    (AgentName.PLANNING, ("plan", "schedule", "roadmap", "organize", "next step")),
    (AgentName.BROWSER, ("browser", "website", "web page", "form", "login")),
    (AgentName.DOCUMENT, ("pdf", "word", "document", "report", "presentation", "spreadsheet")),
    (AgentName.VISION, ("image", "screen", "screenshot", "camera", "ocr", "whiteboard")),
    (AgentName.VOICE, ("voice", "speak", "wake word", "microphone")),
    (AgentName.EMAIL, ("email", "mail", "inbox", "reply")),
    (AgentName.CALENDAR, ("calendar", "meeting", "appointment", "event")),
    (AgentName.SECURITY, ("security", "permission", "password", "secret", "privacy")),
    (AgentName.AUTOMATION, ("open app", "click", "type", "desktop", "automation", "mouse")),
    (AgentName.FILES, ("file", "folder", "download", "upload", "rename")),
    (AgentName.ANALYTICS, ("cpu", "gpu", "ram", "dashboard", "metric", "analytics")),
)


@dataclass(frozen=True)
class AgentRoute:
    agents: list[AgentName]
    rationale: str


class AgentRouter:
    """A deterministic, inspectable router. It never sends request text to a cloud classifier."""

    def route(self, request_text: str) -> AgentRoute:
        text = request_text.lower()
        selected = [agent for agent, words in _KEYWORDS if any(word in text for word in words)]
        if not selected:
            selected = [AgentName.PLANNING]
            rationale = "No specialist keyword matched; planning agent will clarify and coordinate."
        else:
            # A planning agent coordinates requests involving two or more specialists.
            if len(selected) > 1 and AgentName.PLANNING not in selected:
                selected.insert(0, AgentName.PLANNING)
            rationale = "Matched request intent against local specialist routing rules."
        return AgentRoute(agents=selected[:4], rationale=rationale)


class AgentOrchestrator:
    """Runs a user-requested collaboration and stores each final task result."""

    def __init__(
        self,
        model: LLMBackend | ModelRouter,
        memory: MemorySystem,
        tasks: TaskStore,
        audit: AuditLog,
    ):
        self.model = model
        self.memory = memory
        self.tasks = tasks
        self.audit = audit
        self.router = AgentRouter()

    def plan(self, request_text: str) -> dict[str, Any]:
        route = self.router.route(request_text)
        return {"agents": [agent.value for agent in route.agents], "rationale": route.rationale}

    def execute(self, request_text: str, provider_preference: str = "local") -> dict[str, Any]:
        route = self.router.route(request_text)
        task = self.tasks.create(request_text, [agent.value for agent in route.agents])
        task_id = task["id"]
        self.tasks.update(task_id, TaskStatus.RUNNING)
        self.audit.record("agent_task", "started", {"task_id": task_id, "agents": task["agents"]})
        facts = self.memory.long_term.all_facts()
        index = SemanticIndex()
        index.build(facts)
        memory_hits = index.search(request_text, top_k=4)
        results: list[dict[str, str]] = []
        try:
            for agent in route.agents:
                context = "\n".join(f"- {item['key']}: {item['text']}" for item in memory_hits)
                system = (
                    f"You are JARVIS's {agent.value} agent. {_AGENT_INSTRUCTIONS[agent]} "
                    "Keep the answer concise, truthful, privacy-first, and do not perform external actions."
                )
                prompt = f"User request: {request_text}\n\nRelevant local memory:\n{context or '(none)'}"
                if isinstance(self.model, ModelRouter):
                    response = self.model.generate(prompt, system=system, preference=provider_preference)
                else:
                    response = self.model.generate(prompt, system=system)
                results.append({"agent": agent.value, "response": response})
            result = {
                "route": self.plan(request_text),
                "memory_hits": memory_hits,
                "agent_results": results,
                "requires_confirmation_for_actions": True,
            }
            updated = self.tasks.update(task_id, TaskStatus.COMPLETED, result=result)
            self.audit.record("agent_task", "completed", {"task_id": task_id, "agents": task["agents"]})
            return updated or task
        except Exception as exc:  # Capability providers are optional and may be offline.
            updated = self.tasks.update(task_id, TaskStatus.FAILED, error=str(exc))
            self.audit.record("agent_task", "failed", {"task_id": task_id, "error": str(exc)})
            return updated or task
