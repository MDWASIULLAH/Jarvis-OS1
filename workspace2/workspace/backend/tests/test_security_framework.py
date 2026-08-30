from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from app.events import EventBus,EventType
from app.memory_fabric import MemoryManager,MemoryQuery
from app.security_framework import *

def _action(*permissions:Permission,title:str="Install Python",domain:PolicyDomain=PolicyDomain.INSTALLATION)->SecurityAction:return SecurityAction(new_id(),title,permissions,domain,target="https://python.org")

def test_permissions_policy_risk_and_explicit_approval_workflow():
    manager=SecurityManager()
    action=_action(Permission.INSTALL)
    decision=manager.authorize(action)
    pending=manager.request_approval(action,"user")
    granted=manager.decide_approval(pending.approval_id,granted=True,decided_by="user")
    assert decision.allowed and decision.risk.level is RiskLevel.MEDIUM
    assert pending.state is ApprovalState.PENDING and granted.state is ApprovalState.GRANTED

def test_threat_integrity_incident_quarantine_recovery_and_audit():
    manager=SecurityManager()
    action=_action(Permission.ADMINISTRATOR,title="unsafe rm -rf")
    threats=manager.detect_threats(action);incident=manager.create_incident(threats[0],("filesystem",));manager.quarantine("unsafe-target");recovery=manager.recover(incident.incident_id)
    bad=manager.verify_integrity("download",expected_hash="a",actual_hash="b")
    audit=manager.create_audit(action,"warning","unsafe command")
    assert threats[0].level is RiskLevel.CRITICAL and recovery.requires_approval
    assert bad.verified is False and manager.audit_history("unsafe")[0]==audit

def test_trust_memory_events_dependency_provider_and_compatibility():
    bus=EventBus();events=[];bus.subscribe(None,lambda event:events.append(event.event_type));memory=MemoryManager()
    class Provider(PolicyProvider):
        def policies(self):return (SecurityPolicy("install",PolicyDomain.INSTALLATION,(Permission.INSTALL,),RiskLevel.HIGH),)
    manager=SecurityManager(policy_provider=Provider(),event_bus=bus,memory_manager=memory,installation=object(),company=object(),mission_control=object())
    action=_action(Permission.INSTALL);report=manager.generate_report(action);record=manager.record_history(action);trust=manager.set_trust("python.org",.9,"official")
    assert report.decision.allowed and record and memory.search(MemoryQuery(text="Security")).matches
    assert trust.score==.9 and manager.trust("python.org")==trust
    assert {EventType.SECURITY_CHECK_STARTED,EventType.SECURITY_CHECK_COMPLETED,EventType.AUDIT_RECORDED}<=set(events)

def test_concurrent_evaluation_and_completed_system_compatibility():
    manager=SecurityManager();action=_action(Permission.READ,domain=PolicyDomain.MEMORY)
    with ThreadPoolExecutor(max_workers=8) as executor:reports=list(executor.map(lambda _:manager.evaluate(action),range(20)))
    from app.installation import InstallationManager
    from app.company import CompanyManager
    assert len(reports)==20 and InstallationManager() and CompanyManager()
