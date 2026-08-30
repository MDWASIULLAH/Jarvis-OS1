"""Immutable policy, approval, risk, trust, and audit contracts."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
class Permission(str,Enum): READ="read"; WRITE="write"; EXECUTE="execute"; INSTALL="install"; CONFIGURE="configure"; NETWORK="network"; BROWSER="browser"; DEPLOYMENT="deployment"; SYSTEM="system"; ADMINISTRATOR="administrator"
class RiskLevel(str,Enum): NONE="none"; LOW="low"; MEDIUM="medium"; HIGH="high"; CRITICAL="critical"
class ApprovalState(str,Enum): PENDING="pending"; GRANTED="granted"; DENIED="denied"
class PolicyDomain(str,Enum): INSTALLATION="installation"; DEPLOYMENT="deployment"; NETWORK="network"; BROWSER="browser"; FILESYSTEM="filesystem"; MEMORY="memory"; PLUGINS="plugins"; MODELS="models"; EXTERNAL_API="external_api"; CONNECTORS="connectors"
@dataclass(frozen=True)
class SecurityAction: action_id:str; title:str; permissions:tuple[Permission,...]; domain:PolicyDomain; target:str=""; metadata:tuple[tuple[str,str],...]=()
@dataclass(frozen=True)
class SecurityPolicy: policy_id:str; domain:PolicyDomain; allowed_permissions:tuple[Permission,...]; max_risk:RiskLevel=RiskLevel.MEDIUM; enabled:bool=True
@dataclass(frozen=True)
class RiskAssessment: level:RiskLevel; rationale:tuple[str,...]
@dataclass(frozen=True)
class PolicyDecision: allowed:bool; rationale:tuple[str,...]; risk:RiskAssessment
@dataclass(frozen=True)
class ApprovalRecord: approval_id:str; action_id:str; state:ApprovalState=ApprovalState.PENDING; requested_by:str=""; decided_by:str=""; rationale:str=""; created_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc))
@dataclass(frozen=True)
class TrustScore: subject_id:str; score:float=0.5; rationale:str=""
@dataclass(frozen=True)
class IntegrityResult: target:str; verified:bool; algorithm:str="sha256"; rationale:str=""
@dataclass(frozen=True)
class Threat: threat_id:str; action_id:str; level:RiskLevel; rationale:str
@dataclass(frozen=True)
class AuditRecord: record_id:str; action_id:str; event:str; detail:str; timestamp:datetime=field(default_factory=lambda:datetime.now(timezone.utc))
@dataclass(frozen=True)
class Incident: incident_id:str; threat_id:str; severity:RiskLevel; affected_components:tuple[str,...]; timeline:tuple[str,...]=(); resolved:bool=False
@dataclass(frozen=True)
class RecoveryPlan: recovery_id:str; incident_id:str|None; actions:tuple[str,...]; requires_approval:bool=True
@dataclass(frozen=True)
class SandboxRequest: request_id:str; sandbox_type:str; purpose:str; execute:bool=False
@dataclass(frozen=True)
class SecurityReport: action_id:str; decision:PolicyDecision; approval:ApprovalRecord|None; threats:tuple[Threat,...]; audits:tuple[AuditRecord,...]
def new_id()->str:return str(uuid.uuid4())
