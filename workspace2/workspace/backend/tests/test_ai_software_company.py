from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType
from app.company import CompanyManager, CompanyRegistry, CompanyRole, CompanyTask, DepartmentKind, Project, ReviewKind
from app.memory_fabric import MemoryManager, MemoryQuery
from app.mission_control import MissionManager
from app.swarm import SwarmManager


def _context(): return ContextManager().create(ContextCreateRequest(ContextKind.MISSION, ContextIdentity(user_id="u1", correlation_id="company-correlation")))


def test_project_lifecycle_departments_roles_swarm_and_mission_integration():
    bus = EventBus(); swarm = SwarmManager(event_bus=bus); missions = MissionManager(event_bus=bus, swarm=swarm)
    manager = CompanyManager(event_bus=bus, swarm=swarm, mission_control=missions)
    project = manager.create_project("JARVIS", "Ship platform", context=_context())
    department = manager.create_department(project.project_id, DepartmentKind.ENGINEERING)
    staffed = manager.assign_team(department.department_id, (CompanyRole.SOLUTION_ARCHITECT, CompanyRole.BACKEND_ENGINEER))

    assert project.mission_id is not None
    assert staffed.roles == (CompanyRole.SOLUTION_ARCHITECT, CompanyRole.BACKEND_ENGINEER)
    assert len(swarm.registry.discover()) == 2
    assert manager.planner_available is False and manager.executor_available is False


def test_workflow_task_assignment_progress_dashboard_and_memory_integration():
    memory = MemoryManager(); swarm = SwarmManager(); manager = CompanyManager(swarm=swarm, memory_manager=memory)
    project = manager.create_project("Task project", "work")
    department = manager.create_department(project.project_id, DepartmentKind.ENGINEERING)
    manager.assign_roles(department.department_id, (CompanyRole.BACKEND_ENGINEER,))
    task = CompanyTask("task-1", project.project_id, "Implement", department.department_id, CompanyRole.BACKEND_ENGINEER)
    manager.assign_tasks((task,))
    manager.collect_results(project.project_id, (task.task_id,), persist=True)
    dashboard = manager.dashboard(project.project_id)

    assert manager.track_progress(project.project_id) == 1.0
    assert dashboard.tasks[0].assigned_agent_id is not None
    assert memory.search(MemoryQuery(text="Implement")).matches


def test_quality_gates_reviews_release_and_event_publication():
    bus = EventBus(); events = []; bus.subscribe(None, lambda event: events.append(event.event_type))
    manager = CompanyManager(event_bus=bus)
    project = manager.create_project("Release", "validate")
    review = manager.request_review(project.project_id, ReviewKind.CODE, "director")
    completed = manager.complete_review(review.review_id, approved=True)
    failed = manager.validate_quality(project.project_id, project.quality_gates[0].gate_id, passed=False)
    with pytest.raises(RuntimeError): manager.prepare_release(project.project_id)
    project = manager.validate_quality(project.project_id, failed.quality_gates[0].gate_id, passed=True)
    for gate in project.quality_gates[1:]: project = manager.validate_quality(project.project_id, gate.gate_id, passed=True)
    released = manager.prepare_release(project.project_id)

    assert completed.approved is True and released.lifecycle.value == "completed"
    assert EventType.REVIEW_REQUESTED in events and EventType.REVIEW_COMPLETED in events
    assert EventType.QUALITY_GATE_FAILED in events and EventType.RELEASE_PREPARED in events


def test_registry_factory_dependency_free_and_concurrent_projects_compatible():
    registry = CompanyRegistry(); registry.register_factory("enterprise", lambda title, goal: Project.create(title, f"enterprise:{goal}"))
    project = registry.create("Factory", "goal", factory="enterprise")
    manager = CompanyManager()
    with ThreadPoolExecutor(max_workers=8) as executor:
        projects = list(executor.map(lambda index: manager.create_project(f"P{index}", "parallel"), range(20)))

    from app.reflection import ReflectionManager
    from app.evolution import EvolutionManager
    assert project.goal == "enterprise:goal"
    assert len({item.project_id for item in projects}) == 20
    assert ReflectionManager() and EvolutionManager()
