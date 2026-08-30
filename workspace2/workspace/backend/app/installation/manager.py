"""Approval-gated installation planning. This module never executes system changes."""
from __future__ import annotations
import threading
from dataclasses import replace
from typing import TYPE_CHECKING
from ..contexts.contracts import Context
from ..events.bus import EventBus
from ..events.model import ConfigurationPrepared, DependencyResolved, DownloadPrepared, EnvironmentAnalyzed, InstallationPayload, InstallationPlanned, RollbackPrepared, StorageVerified, VerificationPrepared
from ..memory_fabric import MemoryAttribute, MemoryDraft, MemoryManager, MemoryType
from .models import *
from .providers import EnvironmentProvider, LocalReadOnlyEnvironmentProvider, PackageProvider, RulePackageProvider
if TYPE_CHECKING:
    from ..mission_control.manager import MissionManager

class InstallationRegistry:
    def __init__(self)->None:self._plans={};self._lock=threading.RLock()
    def add(self,plan:InstallationPlan)->InstallationPlan:
        with self._lock:self._plans[plan.plan_id]=plan
        return plan
    def get(self,plan_id:str)->InstallationPlan:
        with self._lock:return self._plans[plan_id]
    def update(self,plan:InstallationPlan,expected_version:int)->InstallationPlan:
        with self._lock:
            current=self._plans[plan.plan_id]
            if current.version!=expected_version:raise ValueError("Stale installation plan")
            updated=replace(plan,version=current.version+1);self._plans[plan.plan_id]=updated;return updated

class InstallationManager:
    def __init__(self,*,registry:InstallationRegistry|None=None,package_provider:PackageProvider|None=None,environment_provider:EnvironmentProvider|None=None,event_bus:EventBus|None=None,memory_manager:MemoryManager|None=None,mission_control:"MissionManager|None"=None,planner:object|None=None,executor:object|None=None,company:object|None=None)->None:
        self._registry=registry or InstallationRegistry();self._packages=package_provider or RulePackageProvider();self._environment=environment_provider or LocalReadOnlyEnvironmentProvider();self._events=event_bus;self._memory=memory_manager;self._missions=mission_control;self._planner=planner;self._executor=executor;self._company=company
    @property
    def registry(self)->InstallationRegistry:return self._registry
    @property
    def planner_available(self)->bool:return self._planner is not None
    @property
    def executor_available(self)->bool:return self._executor is not None
    def recommended_review_roles(self)->tuple[str,...]: return ("devops_engineer", "platform_engineer", "security_engineer", "qa_engineer")
    def analyze_goal(self,goal:str)->GoalKind:
        text=goal.lower()
        return GoalKind.ANDROID if "android" in text else GoalKind.DOCKER if "docker" in text else GoalKind.AI_DEVELOPMENT if any(x in text for x in ("ai","machine learning","data science")) else GoalKind.PYTHON if "python" in text else GoalKind.VSCODE if "vs code" in text else GoalKind.GENERIC
    def resolve_dependencies(self,packages:tuple[PackageSpec,...])->tuple[PackageSpec,...]:
        resolved={item.package_id:item for item in packages};pending=list(packages)
        while pending:
            item=pending.pop()
            for dependency in item.dependencies:
                if dependency not in resolved: resolved[dependency]=self._packages.package(dependency);pending.append(resolved[dependency])
        return tuple(resolved.values())
    def verify_environment(self)->EnvironmentSnapshot:return self._environment.inspect()
    def estimate_storage(self,packages:tuple[PackageSpec,...],environment:EnvironmentSnapshot)->StorageEstimate:return StorageEstimate(sum(p.download_mb for p in packages),sum(p.installation_mb for p in packages),sum(p.temporary_mb for p in packages),sum(p.cache_mb for p in packages),sum(p.installation_mb for p in packages)*.1,environment.free_storage_mb)
    def check_compatibility(self,packages:tuple[PackageSpec,...],environment:EnvironmentSnapshot)->tuple[CompatibilityFinding,...]:
        return tuple(CompatibilityFinding(item.package_id,CompatibilityState.WARNING if item.package_id=="docker" and not environment.virtualization_supported else CompatibilityState.COMPATIBLE,"Virtualization should be enabled." if item.package_id=="docker" and not environment.virtualization_supported else "Compatible based on available read-only environment data.") for item in packages)
    def prepare_downloads(self,packages:tuple[PackageSpec,...])->tuple[DownloadDescriptor,...]:return tuple(DownloadDescriptor(item.package_id,item.source_url,item.download_mb,item.checksum,item.publisher,item.mirrors,item.resume_supported) for item in packages)
    def analyze_link(self,url:str)->LinkAnalysis:
        official=any(domain in url.lower() for domain in ("microsoft.com","python.org","docker.com","google.com","android.com","github.com"));return LinkAnalysis(url,official,file_type=url.rsplit(".",1)[-1] if "." in url else "unknown",safety_status="official_placeholder" if official else "unverified")
    def configure_environment(self,packages:tuple[PackageSpec,...])->tuple[InstallationAction,...]:return tuple(InstallationAction(new_id(),ActionKind.CONFIGURE,f"Configure PATH and workspace for {item.name}",item.package_id) for item in packages)
    def verify_installation(self,packages:tuple[PackageSpec,...])->tuple[VerificationTask,...]:return tuple(VerificationTask(new_id(),f"Verify {item.name}",f"{item.name} --version") for item in packages)
    def rollback(self,plan:InstallationPlan)->RollbackPlan:
        rollback=RollbackPlan(new_id(),tuple(InstallationAction(new_id(),ActionKind.ROLLBACK,f"Prepare uninstall for {item.name}",item.package_id) for item in plan.packages))
        self._publish(RollbackPrepared,plan,rollback.plan_id);return rollback
    def create_installation_plan(self,goal:str,*,context:Context|None=None)->InstallationPlan:
        kind=self.analyze_goal(goal);environment=self.verify_environment();roots=self._packages.packages_for_goal(goal);packages=self.resolve_dependencies(roots);storage=self.estimate_storage(packages,environment);compatibility=self.check_compatibility(packages,environment);downloads=self.prepare_downloads(packages);configuration=self.configure_environment(packages);verification=self.verify_installation(packages)
        actions=tuple(InstallationAction(new_id(),ActionKind.DOWNLOAD,f"Download {item.name}",item.package_id) for item in packages)+tuple(InstallationAction(new_id(),ActionKind.INSTALL,f"Install {item.name}",item.package_id) for item in packages)+configuration
        mission_id=self._missions.create_mission(f"Installation: {goal}",goal,context=context).mission_id if self._missions else None
        provisional=InstallationPlan(new_id(),goal,kind,packages,environment,storage,compatibility,downloads,actions,verification,RollbackPlan("pending",()),SandboxRequest(new_id(),"Prepare future sandbox validation"),PlanState.AWAITING_APPROVAL if storage.sufficient else PlanState.BLOCKED,mission_id)
        plan=replace(provisional,rollback=self.rollback(provisional));self._registry.add(plan)
        self._publish(EnvironmentAnalyzed,plan);self._publish(DependencyResolved,plan);self._publish(StorageVerified,plan,status="sufficient" if storage.sufficient else "insufficient");self._publish(DownloadPrepared,plan);self._publish(ConfigurationPrepared,plan);self._publish(VerificationPrepared,plan);self._publish(InstallationPlanned,plan)
        return plan
    def approve(self,plan_id:str,*,explicit_approval:bool)->InstallationPlan:
        plan=self._registry.get(plan_id)
        if not explicit_approval:raise PermissionError("Explicit user approval is required before any installation action.")
        if not plan.storage.sufficient:raise RuntimeError("Insufficient storage; choose cleanup or an alternate location before approval.")
        return self._registry.update(replace(plan,state=PlanState.APPROVED),plan.version)
    def create_report(self,plan:InstallationPlan)->InstallationReport:return InstallationReport(plan.plan_id,f"Plan for {plan.goal}: {len(plan.packages)} package(s), all actions require approval.",plan.storage.sufficient,plan.compatibility,True)
    def record_history(self,plan:InstallationPlan,*,context:Context|None=None)->str|None:
        if self._memory is None:return None
        return self._memory.store(MemoryDraft(memory_type=MemoryType.EPISODIC,title=f"Installation plan: {plan.goal}",content=self.create_report(plan).summary,tags=("installation",),metadata=(MemoryAttribute("plan_id",plan.plan_id),)),context=context).memory_id
    def version(self,plan_id:str)->int:return self._registry.get(plan_id).version
    def _publish(self,event_type,plan:InstallationPlan,item_id:str="",status:str="")->None:
        if self._events:self._events.publish(event_type(source="installation_manager",payload=InstallationPayload(plan.plan_id,item_id,status),correlation_id=plan.mission_id or plan.plan_id))
