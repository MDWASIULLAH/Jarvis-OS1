from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType
from app.memory_fabric import MemoryDraft, MemoryManager, MemoryQuery, MemoryType
from app.mission_control import (
    Mission, MissionFilter, MissionLifecycle, MissionManager, NexusFilter, NexusNodeKind,
    ResourceMonitor, ResourceSnapshot, StaticResourceProvider,
)
from app.swarm import AgentKind, AgentMessage, AgentMessageType, SwarmManager, SwarmTask


def _context():
    return ContextManager().create(ContextCreateRequest(ContextKind.MISSION, ContextIdentity(user_id="u1", correlation_id="mission-correlation")))


def test_mission_lifecycle_registry_history_and_event_publication():
    bus = EventBus()
    observed = []
    bus.subscribe(None, lambda event: observed.append(event.event_type))
    manager = MissionManager(event_bus=bus)
    mission = manager.create_mission("Ship", "Release", context=_context())
    paused = manager.pause_mission(mission.mission_id)
    active = manager.resume_mission(mission.mission_id)
    completed = manager.complete_mission(mission.mission_id)
    archived = manager.archive_mission(mission.mission_id)

    assert paused.lifecycle is MissionLifecycle.PAUSED and active.lifecycle is MissionLifecycle.ACTIVE
    assert completed.lifecycle is MissionLifecycle.COMPLETED and archived.lifecycle is MissionLifecycle.ARCHIVED
    assert len(manager.registry.history(mission.mission_id)) == 5
    assert manager.find_missions(MissionFilter(lifecycle=MissionLifecycle.ARCHIVED)) == (archived,)
    assert EventType.MISSION_CREATED in observed and EventType.MISSION_ARCHIVED in observed


def test_timeline_flight_recorder_replay_and_swarm_event_observation():
    bus = EventBus()
    swarm = SwarmManager(event_bus=bus)
    manager = MissionManager(event_bus=bus, swarm=swarm)
    context = _context()
    mission = manager.create_mission("Observe", "Track events", context=context)
    swarm.start(context=context)
    agent = swarm.create_agent(AgentKind.EXECUTIVE, "exec", context=context)
    replay = manager.replay_mission(mission.mission_id)

    assert any(entry.event_type == EventType.AGENT_CREATED.value for entry in replay.timeline)
    assert manager.flight_records(mission.mission_id)
    assert EventType.REPLAY_STARTED.value in {entry.event_type for entry in manager.timeline(mission.mission_id)}
    assert agent.agent_id


def test_communication_agent_inspection_metrics_resources_and_memory():
    context = _context()
    swarm = SwarmManager()
    memory = MemoryManager()
    memory.store(MemoryDraft(memory_type=MemoryType.SEMANTIC, title="Mission note", content="inspect me"), context=context)
    resources = ResourceMonitor(StaticResourceProvider(ResourceSnapshot(cpu_percent=11.0, memory_mb=42.0, disk_percent=10.0)))
    manager = MissionManager(swarm=swarm, memory_manager=memory, resource_monitor=resources)
    mission = manager.create_mission("Inspect", "Agents", context=context)
    executive = swarm.create_agent(AgentKind.EXECUTIVE, "exec", context=context)
    worker = swarm.create_agent(AgentKind.WORKER, "worker", parent_agent_id=executive.agent_id, context=context)
    task = SwarmTask.create("Task", "Do it")
    manager.record_task(mission.mission_id, task, worker.agent_id)
    manager.record_communication(mission.mission_id, AgentMessage.create(AgentMessageType.REQUEST, worker.agent_id, "help", context.identity.correlation_id, recipient_agent_id=executive.agent_id))
    inspections = manager.inspect_mission(mission.mission_id)

    assert next(item for item in inspections if item.agent_id == executive.agent_id).child_agent_ids == (worker.agent_id,)
    assert next(item for item in inspections if item.agent_id == worker.agent_id).assigned_task_ids == (task.task_id,)
    assert manager.metrics(mission.mission_id).active_agents == 2
    assert manager.resource_snapshot().memory_mb == 42.0
    assert manager.read_memory(MemoryQuery(text="inspect")).matches


def test_neural_nexus_graph_snapshots_filtering_expansion_collapse_and_replay():
    context = _context()
    swarm = SwarmManager()
    manager = MissionManager(swarm=swarm)
    mission = manager.create_mission("Graph", "Nexus", context=context)
    executive = swarm.create_agent(AgentKind.EXECUTIVE, "exec", context=context)
    worker = swarm.create_agent(AgentKind.WORKER, "worker", parent_agent_id=executive.agent_id, context=context)
    task = SwarmTask.create("Graph task", "node")
    manager.record_task(mission.mission_id, task, worker.agent_id)
    snapshot = manager.graph_snapshot(mission.mission_id)
    filtered = manager.nexus.filter(snapshot, NexusFilter(kinds=(NexusNodeKind.WORKER_AGENT,)))

    assert any(node.node_id == mission.mission_id for node in snapshot.nodes)
    assert filtered.nodes[0].node_id == worker.agent_id
    assert manager.nexus.expand(snapshot, executive.agent_id)
    assert all(node.node_id != worker.agent_id for node in manager.nexus.collapse(snapshot, worker.agent_id).nodes)
    assert manager.replay_mission(mission.mission_id).snapshots


def test_concurrent_missions_and_backward_compatibility():
    manager = MissionManager()
    with ThreadPoolExecutor(max_workers=8) as executor:
        missions = list(executor.map(lambda index: manager.create_mission(f"M{index}", "parallel"), range(20)))

    from app.reflection import ReflectionManager
    from app.evolution import EvolutionManager
    assert len({mission.mission_id for mission in missions}) == 20
    assert all(manager.version(mission.mission_id) == 1 for mission in missions)
    assert ReflectionManager() and EvolutionManager()


def test_registry_factory_supports_dependency_injection():
    from app.mission_control import MissionDependencies, MissionRegistry
    registry = MissionRegistry(MissionDependencies({"region": "test"}))
    registry.register_factory("injected", lambda title, description, dependencies: Mission.create(title, f"{description}:{dependencies.require('region')}"))

    mission = registry.create("injected", "Factory", "created")
    assert mission.description == "created:test"
