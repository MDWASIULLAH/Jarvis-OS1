"""Mission lifecycle and operational awareness; it never performs execution."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ..contexts.contracts import Context
from ..events.bus import EventBus, Subscription
from ..events.model import (
    GraphUpdated, MissionArchived, MissionCancelled, MissionCompleted, MissionCreated,
    MissionPayload, MissionUpdated, ReplayCompleted, ReplayStarted,
)
from ..memory_fabric import MemoryManager, MemoryQuery, MemorySearchResponse
from .models import (
    AgentInspection, CommunicationRecord, Mission, MissionFilter, MissionLifecycle,
    MissionMetrics, MissionReplay, NexusSnapshot, ResourceSnapshot,
)
from .monitors import CommunicationMonitor, FlightRecorder, MetricsManager, MissionTimeline, ResourceMonitor
from .nexus import NeuralNexus
from .registry import MissionRegistry

if TYPE_CHECKING:
    from ..events.model import DomainEvent
    from ..swarm.manager import SwarmManager
    from ..swarm.models import AgentMessage, SwarmTask


class MissionManager:
    """An event-driven operations façade over completed architectural systems."""

    def __init__(self, *, registry: MissionRegistry | None = None, event_bus: EventBus | None = None, swarm: "SwarmManager | None" = None, memory_manager: MemoryManager | None = None, timeline: MissionTimeline | None = None, recorder: FlightRecorder | None = None, communication_monitor: CommunicationMonitor | None = None, metrics_manager: MetricsManager | None = None, resource_monitor: ResourceMonitor | None = None, nexus: NeuralNexus | None = None) -> None:
        self._registry = registry or MissionRegistry()
        self._event_bus = event_bus
        self._swarm = swarm
        self._memory_manager = memory_manager
        self._timeline = timeline or MissionTimeline()
        self._recorder = recorder or FlightRecorder()
        self._communications = communication_monitor or CommunicationMonitor()
        self._metrics = metrics_manager or MetricsManager()
        self._resources = resource_monitor or ResourceMonitor()
        self._nexus = nexus or NeuralNexus()
        self._task_assignments: dict[str, dict[str, str]] = {}
        self._subscription: Subscription | None = event_bus.subscribe(None, self.observe_event, name="mission_control_observer") if event_bus is not None else None

    @property
    def registry(self) -> MissionRegistry: return self._registry
    @property
    def nexus(self) -> NeuralNexus: return self._nexus

    def create_mission(self, title: str, description: str, *, context: Context | None = None) -> Mission:
        mission = Mission.create(title, description, context_id=context.context_id if context else None, correlation_id=context.identity.correlation_id if context else "")
        if not mission.correlation_id:
            mission = replace(mission, correlation_id=mission.mission_id)
        self._registry.register(mission)
        self._publish(MissionCreated, mission)
        return mission

    def update_mission(self, mission_id: str, *, title: str | None = None, description: str | None = None, lifecycle: MissionLifecycle | None = None) -> Mission:
        current = self._registry.get(mission_id)
        updated = self._registry.update(replace(current, title=title or current.title, description=description or current.description, lifecycle=lifecycle or current.lifecycle), expected_version=current.version)
        self._publish(MissionUpdated, updated)
        return updated

    def pause_mission(self, mission_id: str) -> Mission: return self.update_mission(mission_id, lifecycle=MissionLifecycle.PAUSED)
    def resume_mission(self, mission_id: str) -> Mission: return self.update_mission(mission_id, lifecycle=MissionLifecycle.ACTIVE)

    def complete_mission(self, mission_id: str) -> Mission:
        mission = self.update_mission(mission_id, lifecycle=MissionLifecycle.COMPLETED)
        self._publish(MissionCompleted, mission)
        return mission

    def cancel_mission(self, mission_id: str) -> Mission:
        mission = self.update_mission(mission_id, lifecycle=MissionLifecycle.CANCELLED)
        self._publish(MissionCancelled, mission)
        return mission

    def archive_mission(self, mission_id: str) -> Mission:
        mission = self.update_mission(mission_id, lifecycle=MissionLifecycle.ARCHIVED)
        self._publish(MissionArchived, mission)
        return mission

    def replay_mission(self, mission_id: str) -> MissionReplay:
        mission = self._registry.get(mission_id)
        self._publish(ReplayStarted, mission)
        replay = MissionReplay(mission_id, self._timeline.entries(mission_id), self._nexus.snapshots(mission_id))
        self._publish(ReplayCompleted, mission)
        return replay

    def inspect_mission(self, mission_id: str) -> tuple[AgentInspection, ...]:
        self._registry.get(mission_id)
        agents = self._agents()
        timeline = self._timeline.entries(mission_id)
        assignments = self._task_assignments.get(mission_id, {})
        inspections = []
        for agent in agents:
            agent_id = getattr(agent, "agent_id")
            children = tuple(getattr(item, "agent_id") for item in agents if getattr(item, "parent_agent_id", None) == agent_id)
            messages = self._communications.search(mission_id)
            inspections.append(AgentInspection(
                agent_id, getattr(agent, "name"), getattr(agent, "parent_agent_id", None), children,
                getattr(getattr(agent, "lifecycle"), "value", "unknown"),
                tuple(task_id for task_id, assigned_agent in assignments.items() if assigned_agent == agent_id),
                tuple(item.capability_id for item in getattr(agent, "capabilities", ())),
                getattr(getattr(agent, "health"), "score", 0.0), getattr(getattr(agent, "health"), "cpu_percent", 0.0),
                getattr(getattr(agent, "health"), "memory_mb", 0.0),
                sum(record.sender_agent_id == agent_id or record.recipient_agent_id == agent_id for record in messages),
                tuple(entry for entry in timeline if agent_id in entry.detail),
            ))
        return tuple(inspections)

    def export_mission(self, mission_id: str) -> MissionReplay: return self.replay_mission(mission_id)
    def version(self, mission_id: str) -> int: return self._registry.get(mission_id).version
    def find_missions(self, query: MissionFilter = MissionFilter()) -> tuple[Mission, ...]: return self._registry.find(query)
    def timeline(self, mission_id: str): return self._timeline.entries(mission_id)
    def flight_records(self, mission_id: str): return self._recorder.replay(mission_id)
    def resource_snapshot(self) -> ResourceSnapshot: return self._resources.snapshot()
    def metrics(self, mission_id: str) -> MissionMetrics: return self._metrics.collect(self._agents(), self._timeline.entries(mission_id))

    def graph_snapshot(self, mission_id: str) -> NexusSnapshot:
        mission = self._registry.get(mission_id)
        snapshot = self._nexus.build(mission_id, mission.title, self._agents(), tuple(self._task_assignments.get(mission_id, {})))
        self._publish(GraphUpdated, mission, snapshot_id=snapshot.snapshot_id)
        return snapshot

    def record_communication(self, mission_id: str, message: "AgentMessage") -> CommunicationRecord:
        record = CommunicationRecord(mission_id, message.message_id, message.message_type.value, message.sender_agent_id, message.recipient_agent_id, message.content)
        return self._communications.record(record)

    def record_task(self, mission_id: str, task: "SwarmTask", agent_id: str | None = None) -> None:
        if agent_id is not None: self._task_assignments.setdefault(mission_id, {})[task.task_id] = agent_id
        else: self._task_assignments.setdefault(mission_id, {}).setdefault(task.task_id, "")

    def read_memory(self, query: MemoryQuery) -> MemorySearchResponse:
        if self._memory_manager is None: raise LookupError("Memory Fabric is not configured.")
        return self._memory_manager.search(query)

    def observe_event(self, event: "DomainEvent[Any]") -> None:
        for mission in self._registry.find():
            if mission.correlation_id and mission.correlation_id != event.correlation_id:
                continue
            entry = self._timeline.record(mission.mission_id, event, detail=self._event_detail(event))
            self._recorder.record(entry)
            payload = getattr(event, "payload", None)
            task_id, agent_id = getattr(payload, "task_id", ""), getattr(payload, "agent_id", "")
            if task_id and agent_id: self._task_assignments.setdefault(mission.mission_id, {})[task_id] = agent_id

    def close(self) -> None:
        if self._event_bus is not None and self._subscription is not None:
            self._event_bus.unsubscribe(self._subscription)
            self._subscription = None

    def _agents(self) -> tuple[object, ...]:
        return self._swarm.registry.discover() if self._swarm is not None else ()

    @staticmethod
    def _event_detail(event: "DomainEvent[Any]") -> str:
        payload = getattr(event, "payload", None)
        return " ".join(str(getattr(payload, item, "")) for item in ("agent_id", "task_id", "mission_id") if getattr(payload, item, ""))

    def _publish(self, event_type, mission: Mission, *, snapshot_id: str = "") -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event_type(source="mission_control", payload=MissionPayload(mission.mission_id, mission.lifecycle.value, snapshot_id), correlation_id=mission.correlation_id or mission.mission_id))
