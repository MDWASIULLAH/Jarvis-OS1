"""Stateful orchestration only; no capability or plan execution occurs here."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ..contexts.contracts import Context
from ..events.bus import EventBus
from ..events.model import (
    AgentAssigned, AgentCompleted, AgentCreated, AgentDestroyed, AgentFailed,
    AgentRecovered, HelperRetired, HelperSpawned, SwarmPayload, SwarmStarted,
    SwarmStopped, TaskDelegated, TaskMerged,
)
from ..memory_fabric import MemoryAttribute, MemoryDraft, MemoryManager, MemoryType
from .models import (
    AgentAssignment, AgentHealth, AgentKind, AgentLifecycle, AgentMessage,
    AgentMessageType, HelperPoolConfiguration, RecoveryRecord, SwarmAgent,
    SwarmResult, SwarmTask, TaskLifecycle, TaskResult,
)
from .registry import AgentRegistry

if TYPE_CHECKING:
    from ..execution.executor import ToolExecutor
    from ..planning.models import ExecutionPlan
    from ..planning.planner import Planner


class SwarmManager:
    """Coordinates agent state and delegation; execution stays downstream."""

    def __init__(self, *, registry: AgentRegistry | None = None, event_bus: EventBus | None = None, helper_pool: HelperPoolConfiguration | None = None, planner: "Planner | None" = None, executor: "ToolExecutor | None" = None, memory_manager: MemoryManager | None = None) -> None:
        self._registry = registry or AgentRegistry()
        self._event_bus = event_bus
        self._helper_pool = helper_pool or HelperPoolConfiguration()
        self._planner = planner  # Capability planning remains owned by Planner.
        self._executor = executor  # Retained integration boundary; never invoked here.
        self._memory_manager = memory_manager
        self._swarm_id = str(uuid.uuid4())
        self._tasks: dict[str, SwarmTask] = {}
        self._assignments: dict[str, AgentAssignment] = {}
        self._messages: list[AgentMessage] = []
        self._recoveries: list[RecoveryRecord] = []
        self._lock = threading.RLock()
        self._started = False

    @property
    def registry(self) -> AgentRegistry: return self._registry
    @property
    def planner_available(self) -> bool: return self._planner is not None
    @property
    def executor_available(self) -> bool: return self._executor is not None

    def start(self, *, context: Context | None = None) -> None:
        with self._lock: self._started = True
        self._publish(SwarmStarted, context=context)

    def stop(self, *, context: Context | None = None) -> None:
        with self._lock: self._started = False
        self._publish(SwarmStopped, context=context)

    def create_agent(self, kind: AgentKind, name: str, *, parent_agent_id: str | None = None, context: Context | None = None) -> SwarmAgent:
        agent = self._registry.create(kind, name, parent_agent_id=parent_agent_id, context_id=context.context_id if context else None)
        self._publish(AgentCreated, agent_id=agent.agent_id, context=context)
        return agent

    def destroy_agent(self, agent_id: str, *, context: Context | None = None) -> SwarmAgent:
        agent = self._registry.remove(agent_id)
        self._publish(AgentDestroyed, agent_id=agent_id, context=context)
        return agent

    def assign_task(self, task: SwarmTask, *, agent_id: str | None = None, context: Context | None = None) -> AgentAssignment:
        with self._lock:
            if any(existing.title == task.title and existing.lifecycle in (TaskLifecycle.PENDING, TaskLifecycle.ASSIGNED) for existing in self._tasks.values()):
                raise ValueError(f"Duplicate active task: {task.title}")
            agent = self._registry.get(agent_id) if agent_id else self._select_agent()
            if agent is None:
                helpers = self.scale_helpers(1, context=context)
                agent = helpers[0] if helpers else None
            if agent is None:
                raise RuntimeError("No ready swarm agent is available.")
            assigned_task = replace(task, lifecycle=TaskLifecycle.ASSIGNED)
            self._tasks[task.task_id] = assigned_task
            assignment = AgentAssignment(agent.agent_id, task.task_id, time.monotonic())
            self._assignments[task.task_id] = assignment
            self._registry.update(replace(agent, lifecycle=AgentLifecycle.BUSY), expected_version=agent.version)
        self._publish(AgentAssigned, agent_id=assignment.agent_id, task_id=task.task_id, context=context)
        self._publish(TaskDelegated, agent_id=assignment.agent_id, task_id=task.task_id, context=context)
        return assignment

    def split_task(self, task: SwarmTask, parts: tuple[SwarmTask, ...]) -> tuple[SwarmTask, ...]:
        return tuple(replace(part, parent_task_id=task.task_id) for part in parts)

    def ingest_plan(self, plan: "ExecutionPlan") -> tuple[SwarmTask, ...]:
        """Maps Planner's existing DAG into delegation records without executing it."""
        return tuple(SwarmTask(step.step_id, step.name, step.description, dependencies=tuple(dep.prerequisite_step_id for dep in step.dependencies), plan_id=plan.plan_id, checkpoint_ids=tuple(checkpoint.checkpoint_id for checkpoint in plan.checkpoints if checkpoint.before_step_id in (None, step.step_id)), rollback_prepared=step.rollback_policy.mode.value != "none") for step in plan.steps)

    def merge_results(self, task_id: str, results: tuple[TaskResult, ...], *, persist: bool = False, context: Context | None = None) -> SwarmResult:
        content = "\n".join(item.content for item in results)
        with self._lock:
            task = self._tasks.get(task_id)
            if task is not None:
                self._tasks[task_id] = replace(task, lifecycle=TaskLifecycle.COMPLETED if all(item.successful for item in results) else TaskLifecycle.FAILED)
        if persist and self._memory_manager is not None:
            self._memory_manager.store(MemoryDraft(memory_type=MemoryType.EPISODIC, title=f"Swarm task: {task_id}", content=content, tags=("swarm",), metadata=(MemoryAttribute("task_id", task_id),)), context=context)
        self._publish(TaskMerged, task_id=task_id, context=context)
        return SwarmResult(task_id, content, results)

    def send_message(self, message: AgentMessage) -> AgentMessage:
        with self._lock: self._messages.append(message)
        return message

    def broadcast(self, sender_agent_id: str, content: str, correlation_id: str) -> tuple[AgentMessage, ...]:
        messages = tuple(AgentMessage.create(AgentMessageType.BROADCAST, sender_agent_id, content, correlation_id, recipient_agent_id=agent.agent_id) for agent in self._registry.discover() if agent.agent_id != sender_agent_id)
        for message in messages: self.send_message(message)
        return messages

    def monitor_agents(self) -> tuple[SwarmAgent, ...]:
        monitored = tuple(self.health_check(agent.agent_id) for agent in self._registry.discover())
        self.retire_idle_helpers()
        return monitored

    def health_check(self, agent_id: str) -> SwarmAgent:
        agent = self._registry.get(agent_id)
        health = agent.health
        score = max(0.0, min(1.0, 1.0 - health.failures * .15 - health.retries * .05 - health.queue_size * .01 - max(0.0, health.cpu_percent - self._helper_pool.cpu_budget_percent) / 100))
        return self._registry.update(replace(agent, health=replace(health, heartbeat_at=time.monotonic(), score=score)), expected_version=agent.version)

    def recover_agent(self, agent_id: str, reason: str, *, context: Context | None = None) -> SwarmAgent:
        agent = self._registry.get(agent_id)
        recovering = self._registry.update(replace(agent, lifecycle=AgentLifecycle.RECOVERING), expected_version=agent.version)
        restored = self._registry.update(replace(recovering, lifecycle=AgentLifecycle.READY), expected_version=recovering.version)
        with self._lock: self._recoveries.append(RecoveryRecord(agent_id, reason, "retry_or_reassign"))
        self._publish(AgentRecovered, agent_id=agent_id, context=context)
        return restored

    def cancel_agent(self, agent_id: str, *, context: Context | None = None) -> SwarmAgent:
        agent = self._registry.get(agent_id)
        cancelled = self._registry.update(replace(agent, lifecycle=AgentLifecycle.CANCELLED), expected_version=agent.version)
        self._publish(AgentFailed, agent_id=agent_id, status="cancelled", context=context)
        return cancelled

    def pause_agent(self, agent_id: str) -> SwarmAgent: return self._transition(agent_id, AgentLifecycle.WAITING)
    def resume_agent(self, agent_id: str) -> SwarmAgent: return self._transition(agent_id, AgentLifecycle.READY)
    def prioritize(self, tasks: tuple[SwarmTask, ...]) -> tuple[SwarmTask, ...]: return tuple(sorted(tasks, key=lambda task: (-task.priority, task.task_id)))
    def rebalance(self, *, context: Context | None = None) -> tuple[SwarmAgent, ...]: return self.scale_helpers(max(0, len(self._tasks) - len(self._registry.discover(lifecycle=AgentLifecycle.READY))), context=context)
    def version(self, agent_id: str) -> int: return self._registry.get(agent_id).version

    def scale_helpers(self, required: int, *, context: Context | None = None) -> tuple[SwarmAgent, ...]:
        active = self._registry.discover(kind=AgentKind.HELPER)
        limits = tuple(limit for limit in (self._helper_pool.maximum_active, self._helper_pool.concurrency_limit) if limit is not None)
        capacity = (min(limits) - len(active)) if limits else required
        count = max(0, min(required, capacity))
        helpers = tuple(self.create_agent(AgentKind.HELPER, f"helper-{len(active) + index + 1}", context=context) for index in range(count))
        for helper in helpers: self._publish(HelperSpawned, agent_id=helper.agent_id, context=context)
        return helpers

    def retire_idle_helpers(self, *, context: Context | None = None) -> tuple[SwarmAgent, ...]:
        retired = []
        helpers = self._registry.discover(kind=AgentKind.HELPER, lifecycle=AgentLifecycle.READY)
        retirement_count = max(0, len(helpers) - self._helper_pool.minimum_active)
        for helper in helpers[:retirement_count]:
            updated = self._transition(helper.agent_id, AgentLifecycle.RETIRED)
            retired.append(updated)
            self._publish(HelperRetired, agent_id=updated.agent_id, context=context)
        return tuple(retired)

    def _select_agent(self) -> SwarmAgent | None:
        candidates = self._registry.discover(lifecycle=AgentLifecycle.READY)
        return next((agent for agent in candidates if agent.kind is not AgentKind.OBSERVER), None)

    def _transition(self, agent_id: str, lifecycle: AgentLifecycle) -> SwarmAgent:
        agent = self._registry.get(agent_id)
        return self._registry.update(replace(agent, lifecycle=lifecycle), expected_version=agent.version)

    def _publish(self, event_type, *, agent_id: str = "", task_id: str = "", status: str = "", context: Context | None = None) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event_type(source="swarm_orchestrator", payload=SwarmPayload(self._swarm_id, agent_id, task_id, status), correlation_id=context.identity.correlation_id if context else self._swarm_id))
