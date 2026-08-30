"""AI Software Company coordination only; engineering work remains downstream."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from ..contexts.contracts import Context
from ..events.bus import EventBus
from ..events.model import CompanyPayload, DepartmentCreated, ProjectCompleted, ProjectCreated, QualityGateFailed, QualityGatePassed, ReleasePrepared, ReviewCompleted, ReviewRequested, RoleAssigned, TaskAssigned
from ..memory_fabric import MemoryAttribute, MemoryDraft, MemoryManager, MemoryType
from ..swarm.models import AgentKind, SwarmTask
from .models import CompanyRole, CompanyTask, Department, DepartmentKind, GateState, Project, ProjectDashboard, ProjectLifecycle, QualityGate, ReviewKind, ReviewReport, WorkflowStage, WorkflowStageKind

if TYPE_CHECKING:
    from ..mission_control.manager import MissionManager
    from ..swarm.manager import SwarmManager


class CompanyRegistry:
    """Instance-scoped registry/factory for projects and enterprise adapters."""
    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}; self._factories: dict[str, Callable[[str, str], Project]] = {}; self._lock = threading.RLock()
    def register_factory(self, name: str, factory: Callable[[str, str], Project]) -> None:
        with self._lock:
            if not name or name in self._factories: raise ValueError(f"Project factory is already registered: {name}")
            self._factories[name] = factory
    def create(self, title: str, goal: str, *, factory: str | None = None) -> Project:
        with self._lock:
            project = self._factories[factory](title, goal) if factory else Project.create(title, goal)
            if project.project_id in self._projects: raise ValueError(f"Project already registered: {project.project_id}")
            self._projects[project.project_id] = project
            return project
    def get(self, project_id: str) -> Project:
        with self._lock:
            try: return self._projects[project_id]
            except KeyError as exc: raise KeyError(f"Unknown project: {project_id}") from exc
    def update(self, project: Project, *, expected_version: int) -> Project:
        with self._lock:
            current = self.get(project.project_id)
            if current.version != expected_version: raise ValueError(f"Stale project version: {project.project_id}")
            updated = replace(project, version=current.version + 1)
            self._projects[project.project_id] = updated
            return updated
    def discover(self) -> tuple[Project, ...]:
        with self._lock: return tuple(self._projects.values())


class CompanyManager:
    def __init__(self, *, registry: CompanyRegistry | None = None, event_bus: EventBus | None = None, swarm: "SwarmManager | None" = None, mission_control: "MissionManager | None" = None, memory_manager: MemoryManager | None = None, planner: object | None = None, executor: object | None = None) -> None:
        self._registry = registry or CompanyRegistry(); self._event_bus = event_bus; self._swarm = swarm; self._missions = mission_control; self._memory = memory_manager; self._planner = planner; self._executor = executor
        self._departments: dict[str, Department] = {}; self._tasks: dict[str, CompanyTask] = {}; self._reviews: dict[str, ReviewReport] = {}; self._role_agents: dict[tuple[str, str, CompanyRole], str] = {}; self._lock = threading.RLock()

    @property
    def registry(self) -> CompanyRegistry: return self._registry
    @property
    def planner_available(self) -> bool: return self._planner is not None
    @property
    def executor_available(self) -> bool: return self._executor is not None

    def create_project(self, title: str, goal: str, *, priority: int = 50, context: Context | None = None) -> Project:
        mission_id = self._missions.create_mission(title, goal, context=context).mission_id if self._missions is not None else None
        project = self._registry.create(title, goal)
        project = self._registry.update(replace(project, priority=priority, mission_id=mission_id, lifecycle=ProjectLifecycle.ACTIVE, workflow=self._default_workflow(), quality_gates=self._default_gates()), expected_version=project.version)
        self._publish(ProjectCreated, project)
        return project

    def create_department(self, project_id: str, kind: DepartmentKind, name: str | None = None) -> Department:
        self._registry.get(project_id)
        department = Department(f"{project_id}:{kind.value}:{len(self._departments) + 1}", project_id, kind, name or kind.value.replace("_", " ").title())
        with self._lock: self._departments[department.department_id] = department
        self._publish(DepartmentCreated, self._registry.get(project_id), department_id=department.department_id)
        return department

    def assign_roles(self, department_id: str, roles: tuple[CompanyRole, ...], *, context: Context | None = None) -> Department:
        with self._lock:
            department = self._departments[department_id]
            agents = []
            for role in roles:
                agent_id = None
                if self._swarm is not None:
                    kind = AgentKind.EXECUTIVE if role in (CompanyRole.CEO, CompanyRole.CTO, CompanyRole.PROJECT_DIRECTOR) else AgentKind.WORKER
                    agent_id = self._swarm.create_agent(kind, role.value, context=context).agent_id
                self._role_agents[(department.project_id, department_id, role)] = agent_id or ""
                agents.append(role)
            updated = replace(department, roles=tuple(dict.fromkeys((*department.roles, *agents))))
            self._departments[department_id] = updated
        for role in roles: self._publish(RoleAssigned, self._registry.get(updated.project_id), department_id=department_id, item_id=role.value)
        return updated

    def assign_team(self, department_id: str, roles: tuple[CompanyRole, ...], *, context: Context | None = None) -> Department: return self.assign_roles(department_id, roles, context=context)
    def create_workflow(self, project_id: str, stages: tuple[WorkflowStage, ...]) -> Project:
        project = self._registry.get(project_id); return self._registry.update(replace(project, workflow=stages), expected_version=project.version)

    def assign_tasks(self, tasks: tuple[CompanyTask, ...], *, context: Context | None = None) -> tuple[CompanyTask, ...]:
        assigned = []
        for task in tasks:
            project = self._registry.get(task.project_id)
            if task.department_id and task.role:
                agent_id = self._role_agents.get((task.project_id, task.department_id, task.role)) or None
                task = replace(task, assigned_agent_id=agent_id)
                if self._swarm is not None and agent_id is not None:
                    self._swarm.assign_task(SwarmTask(task.task_id, task.title, task.title, dependencies=task.dependencies), agent_id=agent_id, context=context)
            with self._lock: self._tasks[task.task_id] = task
            assigned.append(task); self._publish(TaskAssigned, project, department_id=task.department_id or "", item_id=task.task_id)
        return tuple(assigned)

    def track_progress(self, project_id: str) -> float:
        tasks = self._project_tasks(project_id); return sum(task.completed for task in tasks) / len(tasks) if tasks else 0.0
    def collect_results(self, project_id: str, task_ids: tuple[str, ...], *, persist: bool = False, context: Context | None = None) -> tuple[CompanyTask, ...]:
        completed = []
        for task_id in task_ids:
            with self._lock:
                task = self._tasks[task_id]; task = replace(task, completed=True); self._tasks[task_id] = task
            completed.append(task)
        if persist and self._memory is not None:
            self._memory.store(MemoryDraft(memory_type=MemoryType.EPISODIC, title=f"Project results: {project_id}", content="\n".join(task.title for task in completed), tags=("company", "project"), metadata=(MemoryAttribute("project_id", project_id),)), context=context)
        return tuple(completed)

    def validate_quality(self, project_id: str, gate_id: str, *, passed: bool) -> Project:
        project = self._registry.get(project_id)
        gates = tuple(replace(gate, state=GateState.PASSED if passed else GateState.FAILED) if gate.gate_id == gate_id else gate for gate in project.quality_gates)
        if not any(gate.gate_id == gate_id for gate in project.quality_gates): raise KeyError(f"Unknown quality gate: {gate_id}")
        updated = self._registry.update(replace(project, quality_gates=gates), expected_version=project.version)
        self._publish(QualityGatePassed if passed else QualityGateFailed, updated, item_id=gate_id)
        return updated

    def request_review(self, project_id: str, kind: ReviewKind, requested_by: str) -> ReviewReport:
        review = ReviewReport(f"{project_id}:{kind.value}:{len(self._reviews) + 1}", project_id, kind, requested_by)
        with self._lock: self._reviews[review.review_id] = review
        self._publish(ReviewRequested, self._registry.get(project_id), item_id=review.review_id)
        return review

    def complete_review(self, review_id: str, *, approved: bool, findings: tuple[str, ...] = ()) -> ReviewReport:
        with self._lock:
            review = replace(self._reviews[review_id], approved=approved, findings=findings); self._reviews[review_id] = review
        self._publish(ReviewCompleted, self._registry.get(review.project_id), item_id=review_id, status="approved" if approved else "rejected")
        return review

    def prepare_release(self, project_id: str) -> Project:
        project = self._registry.get(project_id)
        if any(gate.required and gate.state is not GateState.PASSED for gate in project.quality_gates): raise RuntimeError("Required quality gates have not passed.")
        project = self._registry.update(replace(project, lifecycle=ProjectLifecycle.COMPLETED), expected_version=project.version)
        self._publish(ReleasePrepared, project); self._publish(ProjectCompleted, project)
        return project

    def dashboard(self, project_id: str) -> ProjectDashboard:
        project = self._registry.get(project_id); return ProjectDashboard(project, tuple(item for item in self._departments.values() if item.project_id == project_id), self._project_tasks(project_id), tuple(item for item in self._reviews.values() if item.project_id == project_id), all(not gate.required or gate.state is GateState.PASSED for gate in project.quality_gates))
    def version(self, project_id: str) -> int: return self._registry.get(project_id).version

    def _project_tasks(self, project_id: str) -> tuple[CompanyTask, ...]:
        with self._lock: return tuple(item for item in self._tasks.values() if item.project_id == project_id)
    @staticmethod
    def _default_workflow() -> tuple[WorkflowStage, ...]: return tuple(WorkflowStage(kind.value, kind) for kind in WorkflowStageKind)
    @staticmethod
    def _default_gates() -> tuple[QualityGate, ...]: return tuple(QualityGate(title.lower().replace(" ", "_"), title) for title in ("Architecture Complete", "Implementation Complete", "Tests Passed", "Performance Verified", "Security Verified", "Documentation Complete", "Deployment Ready", "Production Approved"))
    def _publish(self, event_type, project: Project, *, department_id: str = "", item_id: str = "", status: str = "") -> None:
        if self._event_bus is not None: self._event_bus.publish(event_type(source="ai_software_company", payload=CompanyPayload(project.project_id, department_id, item_id, status), correlation_id=project.mission_id or project.project_id))
