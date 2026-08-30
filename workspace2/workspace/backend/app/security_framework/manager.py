"""Centralized security decisions; deliberately incapable of executing actions."""
from __future__ import annotations
import threading
from dataclasses import replace
from .models import *
from ..events.bus import EventBus
from ..events.model import *
from ..memory_fabric import MemoryManager, MemoryDraft, MemoryAttribute, MemoryType

class PolicyProvider:
    def policies(self)->tuple[SecurityPolicy,...]: raise NotImplementedError
class DefaultPolicyProvider(PolicyProvider):
    def policies(self)->tuple[SecurityPolicy,...]:
        return tuple(SecurityPolicy(domain.value,domain,tuple(Permission),RiskLevel.HIGH) for domain in PolicyDomain)
class SecurityRegistry:
    def __init__(self)->None:self._policies={};self._approvals={};self._audits=[];self._incidents={};self._trust={};self._quarantine=set();self._lock=threading.RLock()
    def add_policy(self,policy:SecurityPolicy)->None:
        with self._lock:self._policies[policy.domain]=policy
    def policy(self,domain:PolicyDomain)->SecurityPolicy:
        with self._lock:return self._policies[domain]

class SecurityManager:
    def __init__(self,*,registry:SecurityRegistry|None=None,policy_provider:PolicyProvider|None=None,event_bus:EventBus|None=None,memory_manager:MemoryManager|None=None,mission_control:object|None=None,installation:object|None=None,company:object|None=None)->None:
        self._registry=registry or SecurityRegistry();self._events=event_bus;self._memory=memory_manager;self._missions=mission_control;self._installation=installation;self._company=company
        for policy in (policy_provider or DefaultPolicyProvider()).policies():
            try:self._registry.add_policy(policy)
            except Exception:pass
    @property
    def registry(self)->SecurityRegistry:return self._registry
    def classify_risk(self,action:SecurityAction)->RiskAssessment:
        text=(action.title+" "+action.target).lower(); reasons=[]; level=RiskLevel.LOW
        if any(term in text for term in ("rm -rf","format","delete all","credential","unsafe")):level=RiskLevel.CRITICAL;reasons.append("Destructive, credential, or unsafe indicator detected.")
        elif Permission.ADMINISTRATOR in action.permissions or Permission.SYSTEM in action.permissions:level=RiskLevel.HIGH;reasons.append("Privileged system permission requested.")
        elif any(permission in action.permissions for permission in (Permission.INSTALL,Permission.CONFIGURE,Permission.DEPLOYMENT,Permission.NETWORK,Permission.BROWSER)):level=RiskLevel.MEDIUM;reasons.append("Privileged environment or external access requested.")
        return RiskAssessment(level,tuple(reasons or ["Read-only or low-impact action."]))
    def validate_policy(self,action:SecurityAction)->PolicyDecision:
        policy=self._registry.policy(action.domain);risk=self.classify_risk(action);rank={RiskLevel.NONE:0,RiskLevel.LOW:1,RiskLevel.MEDIUM:2,RiskLevel.HIGH:3,RiskLevel.CRITICAL:4}
        allowed=policy.enabled and set(action.permissions).issubset(policy.allowed_permissions) and rank[risk.level]<=rank[policy.max_risk]
        rationale=() if allowed else ("Policy is disabled, permissions exceed policy, or risk exceeds policy maximum.",)
        return PolicyDecision(allowed,rationale or ("Policy validation passed.",),risk)
    def evaluate(self,action:SecurityAction)->SecurityReport:
        self._publish(SecurityCheckStarted,action.action_id);decision=self.validate_policy(action);threats=self.detect_threats(action);audit=self.create_audit(action,"policy_allowed" if decision.allowed else "policy_denied","; ".join(decision.rationale));self._publish(SecurityCheckCompleted,action.action_id,status="allowed" if decision.allowed else "denied")
        if not decision.allowed:self._publish(PolicyViolation,action.action_id)
        return SecurityReport(action.action_id,decision,None,threats,(audit,))
    def authorize(self,action:SecurityAction)->PolicyDecision:return self.evaluate(action).decision
    def request_approval(self,action:SecurityAction,requested_by:str)->ApprovalRecord:
        decision=self.validate_policy(action);state=ApprovalState.PENDING if decision.allowed else ApprovalState.DENIED;approval=ApprovalRecord(new_id(),action.action_id,state,requested_by,rationale="Explicit approval required." if decision.allowed else "; ".join(decision.rationale))
        with self._registry._lock:self._registry._approvals[approval.approval_id]=approval
        self._publish(ApprovalRequested,action.action_id,approval.approval_id)
        if state is ApprovalState.DENIED:self._publish(ApprovalDenied,action.action_id,approval.approval_id)
        return approval
    def decide_approval(self,approval_id:str,*,granted:bool,decided_by:str)->ApprovalRecord:
        with self._registry._lock:
            current=self._registry._approvals[approval_id]
            if current.state is not ApprovalState.PENDING:raise ValueError("Approval already decided.")
            updated=replace(current,state=ApprovalState.GRANTED if granted else ApprovalState.DENIED,decided_by=decided_by);self._registry._approvals[approval_id]=updated
        self._publish(ApprovalGranted if granted else ApprovalDenied,updated.action_id,approval_id);self.create_audit(SecurityAction(updated.action_id,"approved action",(),PolicyDomain.FILESYSTEM),"approval_granted" if granted else "approval_denied",decided_by);return updated
    def verify_integrity(self,target:str,*,expected_hash:str|None=None,actual_hash:str|None=None)->IntegrityResult:return IntegrityResult(target,expected_hash is None or expected_hash==actual_hash,rationale="Checksum comparison only; no file access performed.")
    def detect_threats(self,action:SecurityAction)->tuple[Threat,...]:
        risk=self.classify_risk(action)
        if risk.level in (RiskLevel.HIGH,RiskLevel.CRITICAL):
            threat=Threat(new_id(),action.action_id,risk.level,"; ".join(risk.rationale));self._publish(ThreatDetected,action.action_id,threat.threat_id);return (threat,)
        return ()
    def create_incident(self,threat:Threat,components:tuple[str,...])->Incident:
        incident=Incident(new_id(),threat.threat_id,threat.level,components,(threat.rationale,))
        with self._registry._lock:self._registry._incidents[incident.incident_id]=incident
        self._publish(IncidentCreated,threat.action_id,incident.incident_id);return incident
    def quarantine(self,target:str)->None:
        with self._registry._lock:self._registry._quarantine.add(target)
    def recover(self,incident_id:str|None=None)->RecoveryPlan:
        plan=RecoveryPlan(new_id(),incident_id,("Prepare rollback.","Prepare restore reference.","Require explicit approval before recovery execution."));self._publish(RecoveryPrepared,incident_id or "recovery",plan.recovery_id);return plan
    def create_audit(self,action:SecurityAction,event:str,detail:str)->AuditRecord:
        record=AuditRecord(new_id(),action.action_id,event,detail)
        with self._registry._lock:self._registry._audits.append(record)
        self._publish(AuditRecorded,action.action_id,record.record_id);return record
    def audit_history(self,text:str="")->tuple[AuditRecord,...]:
        with self._registry._lock:items=tuple(self._registry._audits)
        return tuple(item for item in items if not text or text.lower() in item.detail.lower() or text.lower() in item.event.lower())
    def trust(self,subject_id:str)->TrustScore:
        with self._registry._lock:return self._registry._trust.get(subject_id,TrustScore(subject_id))
    def set_trust(self,subject_id:str,score:float,rationale:str)->TrustScore:
        trust=TrustScore(subject_id,max(0,min(1,score)),rationale)
        with self._registry._lock:self._registry._trust[subject_id]=trust
        return trust
    def sandbox_request(self,sandbox_type:str,purpose:str)->SandboxRequest:return SandboxRequest(new_id(),sandbox_type,purpose,False)
    def generate_report(self,action:SecurityAction)->SecurityReport:return self.evaluate(action)
    def record_history(self,action:SecurityAction)->str|None:
        if self._memory is None:return None
        return self._memory.store(MemoryDraft(memory_type=MemoryType.EPISODIC,title=f"Security: {action.title}",content="Security evaluation recorded.",tags=("security",),metadata=(MemoryAttribute("action_id",action.action_id),))).memory_id
    def version(self)->int:return 1
    def _publish(self,event_type,check_id:str,item_id:str="",status:str="")->None:
        if self._events:self._events.publish(event_type(source="security_manager",payload=SecurityPayload(check_id,item_id,status),correlation_id=check_id))
