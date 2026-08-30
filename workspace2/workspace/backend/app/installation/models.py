"""Immutable plan-only contracts for environment provisioning."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum

class GoalKind(str, Enum): VSCODE="vscode"; PYTHON="python"; AI_DEVELOPMENT="ai_development"; ANDROID="android"; DOCKER="docker"; DATA_SCIENCE="data_science"; REACT="react"; FLUTTER="flutter"; GAME_DEVELOPMENT="game_development"; GENERIC="generic"
class PlanState(str, Enum): DRAFT="draft"; AWAITING_APPROVAL="awaiting_approval"; APPROVED="approved"; BLOCKED="blocked"
class ActionKind(str, Enum): DOWNLOAD="download"; INSTALL="install"; CONFIGURE="configure"; VERIFY="verify"; ROLLBACK="rollback"
class CompatibilityState(str, Enum): COMPATIBLE="compatible"; WARNING="warning"; INCOMPATIBLE="incompatible"

@dataclass(frozen=True)
class EnvironmentSnapshot:
    operating_system: str; cpu_cores: int; memory_mb: float; free_storage_mb: float; gpu_name: str=""; gpu_driver: str=""; existing_software: tuple[str,...]=(); path_entries: tuple[str,...]=(); virtualization_supported: bool|None=None; internet_available: bool|None=None
@dataclass(frozen=True)
class PackageSpec:
    package_id: str; name: str; version: str="latest"; dependencies: tuple[str,...]=(); download_mb: float=0; installation_mb: float=0; temporary_mb: float=0; cache_mb: float=0; publisher: str=""; source_url: str=""; checksum: str|None=None; mirrors: tuple[str,...]=(); resume_supported: bool=True
@dataclass(frozen=True)
class StorageEstimate:
    download_mb: float; installation_mb: float; temporary_mb: float; cache_mb: float; update_reserve_mb: float; available_mb: float
    @property
    def required_mb(self)->float: return self.download_mb+self.installation_mb+self.temporary_mb+self.cache_mb+self.update_reserve_mb
    @property
    def sufficient(self)->bool: return self.available_mb>=self.required_mb
@dataclass(frozen=True)
class CompatibilityFinding: package_id:str; state:CompatibilityState; explanation:str
@dataclass(frozen=True)
class DownloadDescriptor: package_id:str; url:str; size_mb:float; checksum:str|None; publisher:str; mirrors:tuple[str,...]=(); resume_supported:bool=True
@dataclass(frozen=True)
class LinkAnalysis: url:str; official_source:bool; content_type:str="unknown"; file_type:str="unknown"; estimated_size_mb:float|None=None; version:str=""; publisher:str=""; safety_status:str="unverified"
@dataclass(frozen=True)
class InstallationAction: action_id:str; kind:ActionKind; title:str; package_id:str|None=None; requires_approval:bool=True; destructive:bool=False
@dataclass(frozen=True)
class VerificationTask: task_id:str; title:str; command_hint:str; required:bool=True
@dataclass(frozen=True)
class RollbackPlan: plan_id:str; uninstall_actions:tuple[InstallationAction,...]; backup_references:tuple[str,...]=(); restore_point_placeholder:bool=True
@dataclass(frozen=True)
class SandboxRequest: request_id:str; purpose:str; required:bool=True
@dataclass(frozen=True)
class InstallationPlan:
    plan_id:str; goal:str; goal_kind:GoalKind; packages:tuple[PackageSpec,...]; environment:EnvironmentSnapshot; storage:StorageEstimate; compatibility:tuple[CompatibilityFinding,...]; downloads:tuple[DownloadDescriptor,...]; actions:tuple[InstallationAction,...]; verification:tuple[VerificationTask,...]; rollback:RollbackPlan; sandbox_request:SandboxRequest; state:PlanState=PlanState.DRAFT; mission_id:str|None=None; version:int=1
@dataclass(frozen=True)
class InstallationReport: plan_id:str; summary:str; storage_sufficient:bool; compatibility:tuple[CompatibilityFinding,...]; approval_required:bool=True
def new_id()->str:return str(uuid.uuid4())
