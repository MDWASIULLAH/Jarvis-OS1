from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType
from app.installation import EnvironmentProvider, EnvironmentSnapshot, InstallationManager, PackageProvider, PackageSpec, PlanState, RulePackageProvider
from app.memory_fabric import MemoryManager, MemoryQuery
from app.mission_control import MissionManager


class FakeEnvironment(EnvironmentProvider):
    def __init__(self, free_storage_mb: float = 20_000) -> None: self.free_storage_mb = free_storage_mb
    def inspect(self) -> EnvironmentSnapshot: return EnvironmentSnapshot("Windows", 8, 16_000, self.free_storage_mb, virtualization_supported=True, internet_available=True)


def _context(): return ContextManager().create(ContextCreateRequest(ContextKind.USER, ContextIdentity(user_id="u1", correlation_id="install-correlation")))


def test_goal_analysis_dependency_resolution_environment_storage_download_and_link():
    manager = InstallationManager(environment_provider=FakeEnvironment())
    plan = manager.create_installation_plan("Android Development")
    link = manager.analyze_link("https://developer.android.com/studio.exe")

    assert plan.goal_kind.value == "android"
    assert {item.package_id for item in plan.packages} >= {"android-studio", "jdk", "android-sdk"}
    assert plan.storage.sufficient and plan.downloads and plan.actions
    assert link.official_source is True and link.file_type == "exe"


def test_storage_blocking_approval_configuration_verification_and_rollback_are_plan_only():
    manager = InstallationManager(environment_provider=FakeEnvironment(1))
    plan = manager.create_installation_plan("Docker Environment")
    with pytest.raises(PermissionError): manager.approve(plan.plan_id, explicit_approval=False)
    with pytest.raises(RuntimeError): manager.approve(plan.plan_id, explicit_approval=True)

    assert plan.state is PlanState.BLOCKED
    assert all(action.requires_approval for action in plan.actions)
    assert plan.verification and plan.rollback.uninstall_actions
    assert manager.create_report(plan).approval_required is True


def test_explicit_approval_mission_memory_events_and_company_review_roles():
    bus = EventBus(); observed = []; bus.subscribe(None, lambda event: observed.append(event.event_type))
    memory = MemoryManager(); missions = MissionManager(event_bus=bus)
    context = _context()
    manager = InstallationManager(event_bus=bus, environment_provider=FakeEnvironment(), memory_manager=memory, mission_control=missions, company=object(), planner=object(), executor=object())
    plan = manager.create_installation_plan("Learn Python", context=context)
    approved = manager.approve(plan.plan_id, explicit_approval=True)
    record = manager.record_history(plan, context=context)

    assert approved.state is PlanState.APPROVED and manager.planner_available and manager.executor_available
    assert record and memory.search(MemoryQuery(text="Learn Python")).matches
    assert missions.registry.get(plan.mission_id)
    assert "security_engineer" in manager.recommended_review_roles()
    assert {EventType.INSTALLATION_PLANNED, EventType.DEPENDENCY_RESOLVED, EventType.ROLLBACK_PREPARED} <= set(observed)


def test_provider_injection_thread_safety_and_completed_architecture_compatibility():
    class CustomPackages(RulePackageProvider): pass
    manager = InstallationManager(package_provider=CustomPackages(), environment_provider=FakeEnvironment())
    with ThreadPoolExecutor(max_workers=8) as executor:
        plans = list(executor.map(lambda _: manager.create_installation_plan("VS Code"), range(20)))

    from app.company import CompanyManager
    from app.evolution import EvolutionManager
    assert len({plan.plan_id for plan in plans}) == 20
    assert CompanyManager() and EvolutionManager()
