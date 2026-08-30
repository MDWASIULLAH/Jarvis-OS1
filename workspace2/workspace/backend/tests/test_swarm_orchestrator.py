from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType
from app.memory_fabric import MemoryManager
from app.planning.models import ExecutionPlan, ExecutionMode, PlanStep
from app.swarm import (
    AgentDependencies, AgentKind, AgentLifecycle, AgentMessage, AgentMessageType,
    AgentRegistry, HardwareProfile, HelperPoolConfiguration, SwarmManager, SwarmTask,
    TaskResult,
)


def test_agent_creation_registry_lifecycle_and_context_integration():
    context = ContextManager().create(ContextCreateRequest(ContextKind.AGENT, ContextIdentity(user_id="u1")))
    manager = SwarmManager()
    agent = manager.create_agent(AgentKind.EXECUTIVE, "executive", context=context)

    assert manager.registry.get(agent.agent_id).lifecycle is AgentLifecycle.READY
    assert agent.context_id == context.context_id
    assert manager.version(agent.agent_id) == 1
    assert manager.pause_agent(agent.agent_id).lifecycle is AgentLifecycle.WAITING
    assert manager.resume_agent(agent.agent_id).lifecycle is AgentLifecycle.READY


def test_dynamic_helper_pool_profiles_scaling_and_idle_retirement():
    configuration = HelperPoolConfiguration.for_profile(HardwareProfile.LOW_END_PC)
    manager = SwarmManager(helper_pool=configuration)
    helpers = manager.scale_helpers(150)
    retired = manager.retire_idle_helpers()

    assert configuration.maximum_active == 100
    assert len(helpers) == 100
    assert len(retired) == 100
    assert all(agent.lifecycle is AgentLifecycle.RETIRED for agent in retired)


def test_assignment_decomposition_dag_ingestion_merge_and_memory_integration():
    memory = MemoryManager()
    manager = SwarmManager(memory_manager=memory)
    worker = manager.create_agent(AgentKind.WORKER, "worker")
    root = SwarmTask.create("root", "parent")
    children = manager.split_task(root, (SwarmTask.create("A", "first"), SwarmTask.create("B", "second", dependencies=("A",))))
    assignment = manager.assign_task(children[0], agent_id=worker.agent_id)
    merged = manager.merge_results(children[0].task_id, (TaskResult(children[0].task_id, worker.agent_id, "done"),), persist=True)
    plan = ExecutionPlan.new("decision", "parallel", (PlanStep("p1", "one", "first", None, execution_mode=ExecutionMode.PARALLEL), PlanStep("p2", "two", "second", None),))
    delegated = manager.ingest_plan(plan)

    assert assignment.agent_id == worker.agent_id and children[0].parent_task_id == root.task_id
    assert merged.content == "done"
    assert memory.search.__self__ is memory
    assert len(delegated) == 2 and delegated[0].plan_id == plan.plan_id


def test_typed_agent_communication_health_recovery_cancellation_and_failover():
    manager = SwarmManager()
    agent = manager.create_agent(AgentKind.WORKER, "worker")
    message = AgentMessage.create(AgentMessageType.REQUEST, agent.agent_id, "status", "corr")
    manager.send_message(message)
    health = manager.health_check(agent.agent_id)
    recovered = manager.recover_agent(agent.agent_id, "transient provider issue")
    cancelled = manager.cancel_agent(agent.agent_id)

    assert message.message_type is AgentMessageType.REQUEST and health.health.score >= 0
    assert recovered.lifecycle is AgentLifecycle.READY
    assert cancelled.lifecycle is AgentLifecycle.CANCELLED


def test_events_and_dependency_injected_registry_factory():
    bus = EventBus()
    events = []
    bus.subscribe(None, lambda event: events.append(event.event_type))
    dependencies = AgentDependencies({"region": "test"})
    registry = AgentRegistry(dependencies)
    created = []
    registry.register_factory(AgentKind.OBSERVER, lambda kind, name, container: created.append(container.require("region")) or AgentRegistry._default_factory(kind, name, container))
    manager = SwarmManager(registry=registry, event_bus=bus)
    manager.start()
    observer = manager.create_agent(AgentKind.OBSERVER, "observer")
    helper = manager.scale_helpers(1)[0]
    manager.destroy_agent(observer.agent_id)
    manager.stop()

    assert created == ["test"]
    assert EventType.SWARM_STARTED in events and EventType.SWARM_STOPPED in events
    assert EventType.AGENT_CREATED in events and EventType.AGENT_DESTROYED in events
    assert EventType.HELPER_SPAWNED in events
    assert helper.kind is AgentKind.HELPER


def test_concurrent_agent_creation_and_backward_compatibility():
    manager = SwarmManager()
    with ThreadPoolExecutor(max_workers=8) as executor:
        agents = list(executor.map(lambda index: manager.create_agent(AgentKind.HELPER, f"h-{index}"), range(20)))

    from app.reflection import ReflectionManager
    from app.evolution import EvolutionManager
    assert len({agent.agent_id for agent in agents}) == 20
    assert ReflectionManager() and EvolutionManager()
