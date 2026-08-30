"""
core/runtime.py

Composition root: builds every shared service exactly once and exposes them
as `runtime`. This file is new -- app/api/routes.py (the original surface)
does not import it and keeps working exactly as it did before; app/api/v1.py
(the new, versioned surface) is the only thing that depends on it.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from ..agents.orchestrator import AgentOrchestrator
from ..brain.cognition import BrainCore
from ..brain.llm_interface import ModelRouter, OpenAICompatibleBackend, get_default_backend
from ..capabilities.desktop_automation import DesktopAutomationModule
from ..capabilities.email_module import EmailModule
from ..capabilities.location_services import LocationService
from ..capabilities.builtins import register_builtin_capabilities
from ..capabilities.contracts import CapabilityContext
from ..capabilities.news_module import NewsModule
from ..capabilities.registry import CapabilityRegistry
from ..capabilities.weather_module import WeatherModule
from ..companions.companions import CompanionService
from ..company.manager import CompanyManager
from ..connectors.store import ConnectorStore
from ..events.bus import EventBus
from ..events.observers import AuditEventObserver
from ..execution.executor import ToolExecutor
from ..goals.manager import GoalManager
from ..knowledge.graph import KnowledgeGraph
from ..knowledge.knowledge_base import KnowledgeBase
from ..memory.memory_store import MemorySystem
from ..memory_fabric import MemoryManager
from ..mission_control.manager import MissionManager
from ..mission_control.monitors import ResourceMonitor, SystemResourceProvider
from ..observability.audit import AuditLog
from ..observability.system_monitor import SystemMonitor
from ..planning.planner import Planner
from ..plugins.registry import PluginRegistry
from ..security.permissions import SecurityGate
from ..security_framework.manager import SecurityManager
from ..swarm.manager import SwarmManager
from ..tasks.store import TaskStore
from ..api.workspace import set_workspace_root
from .config import Settings


class Runtime:
    """Owns every shared, stateful service so routes just borrow references."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._closed = False
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.events = EventBus()

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
        self.refresh_cloud_model()

        self.audit = AuditLog(settings.data_dir / "audit.db")
        self.events.subscribe(None, AuditEventObserver(self.audit).handle, priority=-100, name="audit_event_observer")
        self.tasks = TaskStore(settings.data_dir / "tasks.db")
        self.knowledge = KnowledgeBase(settings.data_dir)
        self.companions = CompanionService(settings.data_dir / "companions.db")
        self.plugins = PluginRegistry()
        self.system_monitor = SystemMonitor()
        self.goals = GoalManager(settings.data_dir / "goals.db")
        set_workspace_root(settings.data_dir / "workspace")
        self._tool_state: dict[str, bool] = {}
        self._tool_state_path = settings.data_dir / "tool_state.json"
        self._load_tool_state()

        # If we fell back to the built-in engine, give it read access to the
        # local knowledge base and memory so its answers are grounded.
        if getattr(local_backend, "kind", "") == "local_engine":
            local_backend.knowledge = self.knowledge
            local_backend.memory = self.memory

        self.agents = AgentOrchestrator(model=self.models, memory=self.memory, tasks=self.tasks, audit=self.audit)

        # Capabilities and Brain Core borrow services above.
        self.location = LocationService()
        self.desktop = DesktopAutomationModule(self.security)
        self.build_connected_capabilities()

        # The Brain Core is built last: it borrows every service above.
        self.brain = BrainCore(self)
        self.capabilities = CapabilityRegistry()
        register_builtin_capabilities(self.capabilities)
        self.capabilities.initialize(
            CapabilityContext(
                {
                    "audit": self.audit,
                    "connectors": self.connectors,
                    "desktop": self.desktop,
                    "email": self.email,
                    "knowledge": self.knowledge,
                    "location": self.location,
                    "media": self.brain.media,
                    "memory": self.memory,
                    "models": self.models,
                    "news": self.news,
                    "security": self.security,
                    "weather": self.weather,
                }
            )
        )
        self.refresh_cloud_model()
        self.build_operations_graph()

    def build_operations_graph(self) -> None:
        """Construct the operations tier: missions, swarm, company, security.

        These managers were fully implemented but never composed, so every
        operational panel in the UI had nothing to read and rendered
        "Unavailable". They are cheap, in-memory, and event-driven: passing the
        live `self.events` bus is what makes Mission Control reflect real
        runtime activity rather than a static snapshot.
        """
        self.graph = KnowledgeGraph()
        self.memory_fabric = MemoryManager(event_bus=self.events)
        self._agent_briefs: dict[str, str] = {}
        self.planner = Planner(self.capabilities, event_bus=self.events)
        self.executor = ToolExecutor(self.capabilities, event_bus=self.events)
        self.swarm = SwarmManager(
            event_bus=self.events,
            planner=self.planner,
            executor=self.executor,
            memory_manager=self.memory_fabric,
        )
        self.missions = MissionManager(
            event_bus=self.events,
            swarm=self.swarm,
            memory_manager=self.memory_fabric,
            resource_monitor=ResourceMonitor(SystemResourceProvider(self.system_monitor, self.settings.data_dir)),
        )
        self.company = CompanyManager(
            event_bus=self.events,
            swarm=self.swarm,
            mission_control=self.missions,
            memory_manager=self.memory_fabric,
            planner=self.planner,
            executor=self.executor,
        )
        self.security_framework = SecurityManager(
            event_bus=self.events,
            memory_manager=self.memory_fabric,
            mission_control=self.missions,
            company=self.company,
        )
        self.bootstrap_operations()

    #: Mission that observes the whole event bus. Its correlation_id is left
    #: empty on purpose -- ``MissionManager.observe_event`` only filters events
    #: when a mission declares a correlation id, so a blank one records
    #: everything the runtime actually does.
    SYSTEM_MISSION_ID = "jarvis-runtime"

    def bootstrap_operations(self) -> None:
        """Populate the operations tier from state that already exists.

        Nothing here is sample data. The mission is this process, the workforce
        roster is the orchestrator's real specialist agents, and the graph nodes
        are the capabilities actually registered in this build. Without it the
        managers start empty and the dashboards have nothing truthful to show.
        """
        from ..agents.orchestrator import AgentName, _AGENT_INSTRUCTIONS
        from ..knowledge.graph_models import EntityType, GraphAttribute, GraphEdge, GraphNode, RelationshipType
        from ..mission_control.models import Mission, MissionAttribute, MissionLifecycle
        from ..swarm.models import AgentKind

        self.missions.registry.register(
            Mission(
                mission_id=self.SYSTEM_MISSION_ID,
                title="JARVIS Runtime",
                description="Live operational record of this JARVIS process: every capability call, agent task, and security decision lands on this mission's timeline.",
                lifecycle=MissionLifecycle.ACTIVE,
                correlation_id="",
                metadata=(
                    MissionAttribute("origin", "composition_root"),
                    MissionAttribute("data_dir", str(self.settings.data_dir)),
                ),
            )
        )

        self.swarm.start()
        executive = self.swarm.create_agent(AgentKind.EXECUTIVE, "JARVIS Executive")
        for name in AgentName:
            agent = self.swarm.create_agent(
                AgentKind.WORKER,
                f"{name.value.replace('_', ' ').title()} Agent",
                parent_agent_id=executive.agent_id,
            )
            self._agent_briefs[agent.agent_id] = _AGENT_INSTRUCTIONS.get(name, "")

        root = self.graph.create_node(
            GraphNode(
                node_id="jarvis",
                entity_type=EntityType.PROJECT,
                label="JARVIS",
                attributes=(GraphAttribute("kind", "runtime"),),
                importance=1.0,
                tags=("runtime",),
            )
        )
        for metadata in self.capabilities.discover():
            node = self.graph.create_node(
                GraphNode(
                    node_id=f"capability:{metadata.name}",
                    entity_type=EntityType.TECHNOLOGY,
                    label=metadata.display_name or metadata.name,
                    attributes=(
                        GraphAttribute("category", metadata.category),
                        GraphAttribute("version", metadata.version),
                        GraphAttribute("description", metadata.description),
                    ),
                    tags=metadata.tags or (metadata.category.lower(),),
                    importance=min(1.0, max(0.1, metadata.priority / 100)) if metadata.priority else 0.5,
                )
            )
            self.graph.create_edge(
                GraphEdge(
                    edge_id=f"jarvis->{node.node_id}",
                    source_node_id=root.node_id,
                    target_node_id=node.node_id,
                    relationship=RelationshipType.CONTAINS,
                )
            )

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

    def refresh_cloud_model(self) -> None:
        """Activate a saved OpenRouter or generic compatible-model connector."""
        openrouter = self.connectors.credentials("openrouter")
        compatible = self.connectors.credentials("cloud_llm")
        if openrouter.get("api_key"):
            base_url, api_key, model = "https://openrouter.ai/api/v1", openrouter["api_key"], openrouter.get("model") or "openai/gpt-4o-mini"
        elif compatible.get("base_url") and compatible.get("api_key"):
            base_url, api_key, model = compatible["base_url"], compatible["api_key"], compatible.get("model") or "gpt-4o-mini"
        else:
            base_url, api_key, model = self.settings.cloud_base_url, self.settings.cloud_api_key, self.settings.cloud_model
        cloud = OpenAICompatibleBackend(base_url, model, api_key) if base_url and model else None
        local_backend = getattr(self.models, "local", get_default_backend()) if hasattr(self, "models") else get_default_backend()
        self.models = ModelRouter(local=local_backend, cloud=cloud, allow_cloud=bool(cloud))
        if "agents" in self.__dict__:
            self.agents.model = self.models
        self.build_connected_capabilities()

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


    def close(self) -> None:
        """Release resources owned by this composition root.

        Runtime is the only owner of the v1 service graph. Closing through this
        method keeps SQLite connections from leaking across application reloads
        and makes test and desktop-process shutdown deterministic.
        """
        if self._closed:
            return
        self._closed = True

        self.capabilities.shutdown()

        # Mission Control holds an event-bus subscription; drop it before the
        # services it observes go away.
        missions = getattr(self, "missions", None)
        if missions is not None:
            missions.close()

        # Close in reverse dependency order. Each persistent service owns its
        # own connection and exposes an idempotent ``close`` method.
        for service_name in ("goals", "companions", "knowledge", "tasks", "audit", "memory"):
            service = getattr(self, service_name, None)
            close = getattr(service, "close", None)
            if callable(close):
                close()


class RuntimeProvider:
    """Lifecycle-aware access point retained under the existing ``runtime`` API.

    API modules historically import ``runtime`` directly. Replacing that
    public reference would force a breaking, cross-cutting route rewrite.
    The provider preserves attribute access while moving construction to the
    FastAPI lifespan. Its lazy fallback keeps existing direct route tests and
    embedded callers working when no ASGI lifespan is active.
    """

    def __init__(self, settings_factory: Callable[[], Settings] = Settings.from_environment):
        self._settings_factory = settings_factory
        self._instance: Runtime | None = None
        self._lock = threading.RLock()

    @property
    def started(self) -> bool:
        with self._lock:
            return self._instance is not None

    def start(self) -> Runtime:
        with self._lock:
            if self._instance is None:
                self._instance = Runtime(self._settings_factory())
            return self._instance

    def get(self) -> Runtime:
        """Return the active runtime, starting it for legacy non-ASGI callers."""
        return self.start()

    def stop(self) -> None:
        with self._lock:
            instance, self._instance = self._instance, None
        if instance is not None:
            instance.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.get(), name)


# Public compatibility surface imported by existing v1 routes. Construction is
# intentionally deferred until application startup or the first legacy access.
runtime = RuntimeProvider()
