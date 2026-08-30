"""
core/runtime.py

Composition root: builds every shared service exactly once and exposes them
as `runtime`. This file is new -- app/api/routes.py (the original surface)
does not import it and keeps working exactly as it did before; app/api/v1.py
(the new, versioned surface) is the only thing that depends on it.
"""

from __future__ import annotations

import json

from ..agents.orchestrator import AgentOrchestrator
from ..brain.cognition import BrainCore
from ..brain.llm_interface import ModelRouter, OpenAICompatibleBackend, get_default_backend
from ..capabilities.desktop_automation import DesktopAutomationModule
from ..capabilities.email_module import EmailModule
from ..capabilities.location_services import LocationService
from ..capabilities.news_module import NewsModule
from ..capabilities.weather_module import WeatherModule
from ..companions.companions import CompanionService
from ..connectors.store import ConnectorStore
from ..goals.manager import GoalManager
from ..knowledge.knowledge_base import KnowledgeBase
from ..memory.memory_store import MemorySystem
from ..observability.audit import AuditLog
from ..observability.system_monitor import SystemMonitor
from ..plugins.registry import PluginRegistry
from ..security.permissions import SecurityGate
from ..tasks.store import TaskStore
from .config import Settings


class Runtime:
    """Owns every shared, stateful service so routes just borrow references."""

    def __init__(self, settings: Settings):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)

        self.memory = MemorySystem(settings.data_dir)
        self.security = SecurityGate()

        # Credentials for external apps (Gmail, GitHub, ...). Built early so
        # every capability below can be constructed from live credentials.
        self.connectors = ConnectorStore(settings.data_dir)

        local_backend = get_default_backend()
        cloud_backend = None
        if settings.cloud_base_url and settings.cloud_model:
            cloud_backend = OpenAICompatibleBackend(
                base_url=settings.cloud_base_url, model=settings.cloud_model, api_key=settings.cloud_api_key
            )
        self.models = ModelRouter(local=local_backend, cloud=cloud_backend, allow_cloud=settings.allow_cloud)

        self.audit = AuditLog(settings.data_dir / "audit.db")
        self.tasks = TaskStore(settings.data_dir / "tasks.db")
        self.knowledge = KnowledgeBase(settings.data_dir)
        self.companions = CompanionService(settings.data_dir / "companions.db")
        self.plugins = PluginRegistry()
        self.system_monitor = SystemMonitor()
        self.goals = GoalManager(settings.data_dir / "goals.db")
        self._tool_state: dict[str, bool] = {}
        self._tool_state_path = settings.data_dir / "tool_state.json"
        self._load_tool_state()

        # If we fell back to the built-in engine, give it read access to the
        # local knowledge base and memory so its answers are grounded.
        if getattr(local_backend, "kind", "") == "local_engine":
            local_backend.knowledge = self.knowledge
            local_backend.memory = self.memory

        self.agents = AgentOrchestrator(model=self.models, memory=self.memory, tasks=self.tasks, audit=self.audit)

        # Capability providers the Brain Core calls as tools. Each one degrades
        # to an honest "not configured" answer instead of inventing data.
        self.location = LocationService()
        self.desktop = DesktopAutomationModule(self.security)
        self.build_connected_capabilities()

        # The Brain Core is built last: it borrows every service above.
        self.brain = BrainCore(self)

    def build_connected_capabilities(self) -> None:
        """(Re)build the capabilities whose behaviour depends on credentials.

        These previously read `settings.owm_api_key` / `settings.news_api_key`,
        which do not exist on Settings -- so they always received None and the
        paid providers were unreachable. They now read the connector store.

        Called again after a connector is saved or removed so a newly connected
        app takes effect immediately, without restarting the server.
        """
        self.weather = WeatherModule(self.connectors.credentials("openweather").get("api_key"))
        self.news = NewsModule(self.connectors.credentials("newsapi").get("api_key"))
        self.email = EmailModule(
            self.security,
            self.models.generate,
            credentials=lambda: self.connectors.credentials("gmail"),
        )

    def _load_tool_state(self) -> None:
        try:
            if self._tool_state_path.exists():
                self._tool_state = json.loads(self._tool_state_path.read_text())
        except (json.JSONDecodeError, OSError):
            self._tool_state = {}

    def _save_tool_state(self) -> None:
        try:
            self._tool_state_path.write_text(json.dumps(self._tool_state, indent=2))
        except OSError:
            pass

    def get_tool_enabled(self, tool_id: str) -> bool:
        return self._tool_state.get(tool_id, True)

    def set_tool_enabled(self, tool_id: str, enabled: bool) -> None:
        self._tool_state[tool_id] = enabled
        self._save_tool_state()


runtime = Runtime(Settings.from_environment())
