"""Strongly typed domain-event model shared by all JARVIS subsystems."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from ..brain.decision_engine import Decision
    from ..brain.intent_router import RoutingResult


class EventType(str, Enum):
    INTENT_RESOLVED = "intent.resolved"
    DECISION_CREATED = "decision.created"
    PLAN_CREATED = "plan.created"
    PLAN_VALIDATED = "plan.validated"
    PLAN_REJECTED = "plan.rejected"
    CAPABILITY_STARTED = "capability.started"
    CAPABILITY_COMPLETED = "capability.completed"
    CAPABILITY_FAILED = "capability.failed"
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_CANCELLED = "execution.cancelled"
    EXECUTION_ROLLED_BACK = "execution.rolled_back"
    EXECUTION_TIMED_OUT = "execution.timed_out"
    MEMORY_READ = "memory.read"
    MEMORY_WRITTEN = "memory.written"
    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_DELETED = "memory.deleted"
    MEMORY_RETRIEVED = "memory.retrieved"
    MEMORY_ARCHIVED = "memory.archived"
    MEMORY_MERGED = "memory.merged"
    MEMORY_RESTORED = "memory.restored"
    REFLECTION_STARTED = "reflection.started"
    REFLECTION_COMPLETED = "reflection.completed"
    REFLECTION_FAILED = "reflection.failed"
    LESSON_GENERATED = "reflection.lesson_generated"
    RECOMMENDATION_GENERATED = "reflection.recommendation_generated"
    EVOLUTION_STARTED = "evolution.started"
    EVOLUTION_COMPLETED = "evolution.completed"
    EVOLUTION_FAILED = "evolution.failed"
    PROPOSAL_GENERATED = "evolution.proposal_generated"
    OPTIMIZATION_SUGGESTED = "evolution.optimization_suggested"
    SWARM_STARTED = "swarm.started"
    SWARM_STOPPED = "swarm.stopped"
    AGENT_CREATED = "swarm.agent_created"
    AGENT_DESTROYED = "swarm.agent_destroyed"
    AGENT_ASSIGNED = "swarm.agent_assigned"
    AGENT_COMPLETED = "swarm.agent_completed"
    AGENT_FAILED = "swarm.agent_failed"
    AGENT_RECOVERED = "swarm.agent_recovered"
    HELPER_SPAWNED = "swarm.helper_spawned"
    HELPER_RETIRED = "swarm.helper_retired"
    TASK_DELEGATED = "swarm.task_delegated"
    TASK_MERGED = "swarm.task_merged"
    MISSION_CREATED = "mission.created"
    MISSION_UPDATED = "mission.updated"
    MISSION_COMPLETED = "mission.completed"
    MISSION_CANCELLED = "mission.cancelled"
    MISSION_ARCHIVED = "mission.archived"
    REPLAY_STARTED = "mission.replay_started"
    REPLAY_COMPLETED = "mission.replay_completed"
    GRAPH_UPDATED = "mission.graph_updated"
    PROJECT_CREATED = "company.project_created"
    PROJECT_COMPLETED = "company.project_completed"
    DEPARTMENT_CREATED = "company.department_created"
    ROLE_ASSIGNED = "company.role_assigned"
    TASK_ASSIGNED = "company.task_assigned"
    REVIEW_REQUESTED = "company.review_requested"
    REVIEW_COMPLETED = "company.review_completed"
    QUALITY_GATE_PASSED = "company.quality_gate_passed"
    QUALITY_GATE_FAILED = "company.quality_gate_failed"
    RELEASE_PREPARED = "company.release_prepared"
    INSTALLATION_PLANNED = "installation.planned"
    DEPENDENCY_RESOLVED = "installation.dependency_resolved"
    ENVIRONMENT_ANALYZED = "installation.environment_analyzed"
    STORAGE_VERIFIED = "installation.storage_verified"
    DOWNLOAD_PREPARED = "installation.download_prepared"
    CONFIGURATION_PREPARED = "installation.configuration_prepared"
    VERIFICATION_PREPARED = "installation.verification_prepared"
    ROLLBACK_PREPARED = "installation.rollback_prepared"
    SECURITY_CHECK_STARTED = "security.check_started"
    SECURITY_CHECK_COMPLETED = "security.check_completed"
    APPROVAL_REQUESTED = "security.approval_requested"
    APPROVAL_GRANTED = "security.approval_granted"
    APPROVAL_DENIED = "security.approval_denied"
    THREAT_DETECTED = "security.threat_detected"
    INCIDENT_CREATED = "security.incident_created"
    RECOVERY_PREPARED = "security.recovery_prepared"
    POLICY_VIOLATION = "security.policy_violation"
    AUDIT_RECORDED = "security.audit_recorded"
    RESPONSE_STARTED = "response.started"
    RESPONSE_COMPLETED = "response.completed"
    RESPONSE_FAILED = "response.failed"
    SEARCH_STARTED = "search.started"
    SEARCH_PROVIDER_STARTED = "search.provider_started"
    SEARCH_PROVIDER_COMPLETED = "search.provider_completed"
    SEARCH_PROVIDER_FAILED = "search.provider_failed"
    SEARCH_COMPLETED = "search.completed"
    SEARCH_CANCELLED = "search.cancelled"
    CONTEXT_CREATED = "context.created"
    CONTEXT_UPDATED = "context.updated"
    CONTEXT_DISPOSED = "context.disposed"
    AGENT_STARTED = "agent.started"
    AGENT_FINISHED = "agent.finished"
    SYSTEM_ERROR = "system.error"


class EventPriority(IntEnum):
    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


@dataclass(frozen=True)
class EventAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class EventMetadata:
    """Trace-friendly metadata without an untyped attributes dictionary."""

    trace_parent_id: str | None = None
    attributes: tuple[EventAttribute, ...] = ()

    def value_for(self, key: str) -> str | None:
        return next((item.value for item in self.attributes if item.key == key), None)

    def with_attribute(self, key: str, value: str) -> "EventMetadata":
        return EventMetadata(self.trace_parent_id, (*self.attributes, EventAttribute(key, value)))


PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True, kw_only=True)
class DomainEvent(Generic[PayloadT]):
    """Base event containing the identity and trace context every event needs."""

    source: str
    payload: PayloadT
    event_type: EventType
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: EventMetadata = field(default_factory=EventMetadata)
    priority: EventPriority = EventPriority.NORMAL


@dataclass(frozen=True)
class PlanCreatedPayload:
    plan_id: str
    decision_id: str | None = None
    step_count: int = 0


@dataclass(frozen=True)
class PlanValidatedPayload:
    plan_id: str
    step_count: int


@dataclass(frozen=True)
class PlanRejectedPayload:
    plan_id: str
    reason: str


@dataclass(frozen=True)
class CapabilityStartedPayload:
    capability: str
    operation: str = ""
    step_id: str | None = None


@dataclass(frozen=True)
class CapabilityCompletedPayload:
    capability: str
    operation: str = ""
    rollback_token: str | None = None
    step_id: str | None = None


@dataclass(frozen=True)
class CapabilityFailedPayload:
    capability: str
    operation: str = ""
    error_type: str = ""
    message: str = ""
    step_id: str | None = None


@dataclass(frozen=True)
class ExecutionStartedPayload:
    execution_id: str
    plan_id: str


@dataclass(frozen=True)
class ExecutionCompletedPayload:
    execution_id: str
    plan_id: str
    state: str


@dataclass(frozen=True)
class ExecutionCancelledPayload:
    execution_id: str
    plan_id: str
    reason: str


@dataclass(frozen=True)
class ExecutionRolledBackPayload:
    execution_id: str
    plan_id: str
    step_count: int


@dataclass(frozen=True)
class ExecutionTimedOutPayload:
    execution_id: str
    plan_id: str
    step_id: str | None = None


@dataclass(frozen=True)
class MemoryReadPayload:
    key: str
    found: bool


@dataclass(frozen=True)
class MemoryWrittenPayload:
    key: str
    category: str = "general"


@dataclass(frozen=True)
class MemoryLifecyclePayload:
    """Stable, provider-neutral payload for Memory Fabric lifecycle events."""

    memory_id: str
    memory_type: str = ""
    related_memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReflectionPayload:
    reflection_id: str
    outcome: str = ""
    item_id: str = ""


@dataclass(frozen=True)
class EvolutionPayload:
    evolution_id: str
    proposal_id: str = ""
    status: str = ""


@dataclass(frozen=True)
class SwarmPayload:
    swarm_id: str
    agent_id: str = ""
    task_id: str = ""
    status: str = ""


@dataclass(frozen=True)
class MissionPayload:
    mission_id: str
    status: str = ""
    snapshot_id: str = ""


@dataclass(frozen=True)
class CompanyPayload:
    project_id: str
    department_id: str = ""
    item_id: str = ""
    status: str = ""


@dataclass(frozen=True)
class InstallationPayload:
    plan_id: str
    item_id: str = ""
    status: str = ""


@dataclass(frozen=True)
class SecurityPayload:
    check_id: str
    item_id: str = ""
    status: str = ""

@dataclass(frozen=True, kw_only=True)
class SecurityCheckStarted(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.SECURITY_CHECK_STARTED, init=False)
@dataclass(frozen=True, kw_only=True)
class SecurityCheckCompleted(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.SECURITY_CHECK_COMPLETED, init=False)
@dataclass(frozen=True, kw_only=True)
class ApprovalRequested(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.APPROVAL_REQUESTED, init=False)
@dataclass(frozen=True, kw_only=True)
class ApprovalGranted(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.APPROVAL_GRANTED, init=False)
@dataclass(frozen=True, kw_only=True)
class ApprovalDenied(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.APPROVAL_DENIED, init=False)
@dataclass(frozen=True, kw_only=True)
class ThreatDetected(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.THREAT_DETECTED, init=False)
@dataclass(frozen=True, kw_only=True)
class IncidentCreated(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.INCIDENT_CREATED, init=False)
@dataclass(frozen=True, kw_only=True)
class RecoveryPrepared(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.RECOVERY_PREPARED, init=False)
@dataclass(frozen=True, kw_only=True)
class PolicyViolation(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.POLICY_VIOLATION, init=False)
@dataclass(frozen=True, kw_only=True)
class AuditRecorded(DomainEvent[SecurityPayload]): event_type: EventType = field(default=EventType.AUDIT_RECORDED, init=False)


@dataclass(frozen=True, kw_only=True)
class InstallationPlanned(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.INSTALLATION_PLANNED, init=False)
@dataclass(frozen=True, kw_only=True)
class DependencyResolved(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.DEPENDENCY_RESOLVED, init=False)
@dataclass(frozen=True, kw_only=True)
class EnvironmentAnalyzed(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.ENVIRONMENT_ANALYZED, init=False)
@dataclass(frozen=True, kw_only=True)
class StorageVerified(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.STORAGE_VERIFIED, init=False)
@dataclass(frozen=True, kw_only=True)
class DownloadPrepared(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.DOWNLOAD_PREPARED, init=False)
@dataclass(frozen=True, kw_only=True)
class ConfigurationPrepared(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.CONFIGURATION_PREPARED, init=False)
@dataclass(frozen=True, kw_only=True)
class VerificationPrepared(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.VERIFICATION_PREPARED, init=False)
@dataclass(frozen=True, kw_only=True)
class RollbackPrepared(DomainEvent[InstallationPayload]): event_type: EventType = field(default=EventType.ROLLBACK_PREPARED, init=False)


@dataclass(frozen=True, kw_only=True)
class ProjectCreated(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.PROJECT_CREATED, init=False)
@dataclass(frozen=True, kw_only=True)
class ProjectCompleted(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.PROJECT_COMPLETED, init=False)
@dataclass(frozen=True, kw_only=True)
class DepartmentCreated(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.DEPARTMENT_CREATED, init=False)
@dataclass(frozen=True, kw_only=True)
class RoleAssigned(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.ROLE_ASSIGNED, init=False)
@dataclass(frozen=True, kw_only=True)
class TaskAssigned(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.TASK_ASSIGNED, init=False)
@dataclass(frozen=True, kw_only=True)
class ReviewRequested(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.REVIEW_REQUESTED, init=False)
@dataclass(frozen=True, kw_only=True)
class ReviewCompleted(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.REVIEW_COMPLETED, init=False)
@dataclass(frozen=True, kw_only=True)
class QualityGatePassed(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.QUALITY_GATE_PASSED, init=False)
@dataclass(frozen=True, kw_only=True)
class QualityGateFailed(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.QUALITY_GATE_FAILED, init=False)
@dataclass(frozen=True, kw_only=True)
class ReleasePrepared(DomainEvent[CompanyPayload]): event_type: EventType = field(default=EventType.RELEASE_PREPARED, init=False)


@dataclass(frozen=True, kw_only=True)
class MissionCreated(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.MISSION_CREATED, init=False)
@dataclass(frozen=True, kw_only=True)
class MissionUpdated(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.MISSION_UPDATED, init=False)
@dataclass(frozen=True, kw_only=True)
class MissionCompleted(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.MISSION_COMPLETED, init=False)
@dataclass(frozen=True, kw_only=True)
class MissionCancelled(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.MISSION_CANCELLED, init=False)
@dataclass(frozen=True, kw_only=True)
class MissionArchived(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.MISSION_ARCHIVED, init=False)
@dataclass(frozen=True, kw_only=True)
class ReplayStarted(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.REPLAY_STARTED, init=False)
@dataclass(frozen=True, kw_only=True)
class ReplayCompleted(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.REPLAY_COMPLETED, init=False)
@dataclass(frozen=True, kw_only=True)
class GraphUpdated(DomainEvent[MissionPayload]):
    event_type: EventType = field(default=EventType.GRAPH_UPDATED, init=False)


@dataclass(frozen=True, kw_only=True)
class SwarmStarted(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.SWARM_STARTED, init=False)
@dataclass(frozen=True, kw_only=True)
class SwarmStopped(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.SWARM_STOPPED, init=False)
@dataclass(frozen=True, kw_only=True)
class AgentCreated(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.AGENT_CREATED, init=False)
@dataclass(frozen=True, kw_only=True)
class AgentDestroyed(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.AGENT_DESTROYED, init=False)
@dataclass(frozen=True, kw_only=True)
class AgentAssigned(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.AGENT_ASSIGNED, init=False)
@dataclass(frozen=True, kw_only=True)
class AgentCompleted(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.AGENT_COMPLETED, init=False)
@dataclass(frozen=True, kw_only=True)
class AgentFailed(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.AGENT_FAILED, init=False)
@dataclass(frozen=True, kw_only=True)
class AgentRecovered(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.AGENT_RECOVERED, init=False)
@dataclass(frozen=True, kw_only=True)
class HelperSpawned(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.HELPER_SPAWNED, init=False)
@dataclass(frozen=True, kw_only=True)
class HelperRetired(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.HELPER_RETIRED, init=False)
@dataclass(frozen=True, kw_only=True)
class TaskDelegated(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.TASK_DELEGATED, init=False)
@dataclass(frozen=True, kw_only=True)
class TaskMerged(DomainEvent[SwarmPayload]):
    event_type: EventType = field(default=EventType.TASK_MERGED, init=False)


@dataclass(frozen=True, kw_only=True)
class EvolutionStarted(DomainEvent[EvolutionPayload]):
    event_type: EventType = field(default=EventType.EVOLUTION_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class EvolutionCompleted(DomainEvent[EvolutionPayload]):
    event_type: EventType = field(default=EventType.EVOLUTION_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class EvolutionFailed(DomainEvent[EvolutionPayload]):
    event_type: EventType = field(default=EventType.EVOLUTION_FAILED, init=False)


@dataclass(frozen=True, kw_only=True)
class ProposalGenerated(DomainEvent[EvolutionPayload]):
    event_type: EventType = field(default=EventType.PROPOSAL_GENERATED, init=False)


@dataclass(frozen=True, kw_only=True)
class OptimizationSuggested(DomainEvent[EvolutionPayload]):
    event_type: EventType = field(default=EventType.OPTIMIZATION_SUGGESTED, init=False)


@dataclass(frozen=True, kw_only=True)
class ReflectionStarted(DomainEvent[ReflectionPayload]):
    event_type: EventType = field(default=EventType.REFLECTION_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class ReflectionCompleted(DomainEvent[ReflectionPayload]):
    event_type: EventType = field(default=EventType.REFLECTION_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class ReflectionFailed(DomainEvent[ReflectionPayload]):
    event_type: EventType = field(default=EventType.REFLECTION_FAILED, init=False)


@dataclass(frozen=True, kw_only=True)
class LessonGenerated(DomainEvent[ReflectionPayload]):
    event_type: EventType = field(default=EventType.LESSON_GENERATED, init=False)


@dataclass(frozen=True, kw_only=True)
class RecommendationGenerated(DomainEvent[ReflectionPayload]):
    event_type: EventType = field(default=EventType.RECOMMENDATION_GENERATED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryCreated(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_CREATED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryUpdated(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_UPDATED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryDeleted(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_DELETED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryRetrieved(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_RETRIEVED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryArchived(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_ARCHIVED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryMerged(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_MERGED, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryRestored(DomainEvent[MemoryLifecyclePayload]):
    event_type: EventType = field(default=EventType.MEMORY_RESTORED, init=False)


@dataclass(frozen=True)
class ResponsePayload:
    response_id: str
    stream: bool = False


@dataclass(frozen=True)
class ResponseFailedPayload:
    response_id: str
    error_type: str
    message: str


@dataclass(frozen=True)
class SearchPayload:
    search_id: str
    provider_id: str = ""
    result_count: int = 0
    status: str = ""


@dataclass(frozen=True)
class ContextPayload:
    context_id: str
    context_kind: str
    parent_context_id: str | None = None


@dataclass(frozen=True)
class AgentPayload:
    agent: str
    task_id: str | None = None


@dataclass(frozen=True)
class SystemErrorPayload:
    error_type: str
    message: str
    component: str


@dataclass(frozen=True, kw_only=True)
class IntentResolved(DomainEvent["RoutingResult"]):
    event_type: EventType = field(default=EventType.INTENT_RESOLVED, init=False)


@dataclass(frozen=True, kw_only=True)
class DecisionCreated(DomainEvent["Decision"]):
    event_type: EventType = field(default=EventType.DECISION_CREATED, init=False)


@dataclass(frozen=True, kw_only=True)
class PlanCreated(DomainEvent[PlanCreatedPayload]):
    event_type: EventType = field(default=EventType.PLAN_CREATED, init=False)


@dataclass(frozen=True, kw_only=True)
class PlanValidated(DomainEvent[PlanValidatedPayload]):
    event_type: EventType = field(default=EventType.PLAN_VALIDATED, init=False)


@dataclass(frozen=True, kw_only=True)
class PlanRejected(DomainEvent[PlanRejectedPayload]):
    event_type: EventType = field(default=EventType.PLAN_REJECTED, init=False)


@dataclass(frozen=True, kw_only=True)
class CapabilityStarted(DomainEvent[CapabilityStartedPayload]):
    event_type: EventType = field(default=EventType.CAPABILITY_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class CapabilityCompleted(DomainEvent[CapabilityCompletedPayload]):
    event_type: EventType = field(default=EventType.CAPABILITY_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class CapabilityFailed(DomainEvent[CapabilityFailedPayload]):
    event_type: EventType = field(default=EventType.CAPABILITY_FAILED, init=False)


@dataclass(frozen=True, kw_only=True)
class ExecutionStarted(DomainEvent[ExecutionStartedPayload]):
    event_type: EventType = field(default=EventType.EXECUTION_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class ExecutionCompleted(DomainEvent[ExecutionCompletedPayload]):
    event_type: EventType = field(default=EventType.EXECUTION_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class ExecutionCancelled(DomainEvent[ExecutionCancelledPayload]):
    event_type: EventType = field(default=EventType.EXECUTION_CANCELLED, init=False)


@dataclass(frozen=True, kw_only=True)
class ExecutionRolledBack(DomainEvent[ExecutionRolledBackPayload]):
    event_type: EventType = field(default=EventType.EXECUTION_ROLLED_BACK, init=False)


@dataclass(frozen=True, kw_only=True)
class ExecutionTimedOut(DomainEvent[ExecutionTimedOutPayload]):
    event_type: EventType = field(default=EventType.EXECUTION_TIMED_OUT, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryRead(DomainEvent[MemoryReadPayload]):
    event_type: EventType = field(default=EventType.MEMORY_READ, init=False)


@dataclass(frozen=True, kw_only=True)
class MemoryWritten(DomainEvent[MemoryWrittenPayload]):
    event_type: EventType = field(default=EventType.MEMORY_WRITTEN, init=False)


@dataclass(frozen=True, kw_only=True)
class ResponseStarted(DomainEvent[ResponsePayload]):
    event_type: EventType = field(default=EventType.RESPONSE_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class ResponseCompleted(DomainEvent[ResponsePayload]):
    event_type: EventType = field(default=EventType.RESPONSE_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class ResponseFailed(DomainEvent[ResponseFailedPayload]):
    event_type: EventType = field(default=EventType.RESPONSE_FAILED, init=False)


@dataclass(frozen=True, kw_only=True)
class SearchStarted(DomainEvent[SearchPayload]):
    event_type: EventType = field(default=EventType.SEARCH_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class SearchProviderStarted(DomainEvent[SearchPayload]):
    event_type: EventType = field(default=EventType.SEARCH_PROVIDER_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class SearchProviderCompleted(DomainEvent[SearchPayload]):
    event_type: EventType = field(default=EventType.SEARCH_PROVIDER_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class SearchProviderFailed(DomainEvent[SearchPayload]):
    event_type: EventType = field(default=EventType.SEARCH_PROVIDER_FAILED, init=False)


@dataclass(frozen=True, kw_only=True)
class SearchCompleted(DomainEvent[SearchPayload]):
    event_type: EventType = field(default=EventType.SEARCH_COMPLETED, init=False)


@dataclass(frozen=True, kw_only=True)
class SearchCancelled(DomainEvent[SearchPayload]):
    event_type: EventType = field(default=EventType.SEARCH_CANCELLED, init=False)


@dataclass(frozen=True, kw_only=True)
class ContextCreated(DomainEvent[ContextPayload]):
    event_type: EventType = field(default=EventType.CONTEXT_CREATED, init=False)


@dataclass(frozen=True, kw_only=True)
class ContextUpdated(DomainEvent[ContextPayload]):
    event_type: EventType = field(default=EventType.CONTEXT_UPDATED, init=False)


@dataclass(frozen=True, kw_only=True)
class ContextDisposed(DomainEvent[ContextPayload]):
    event_type: EventType = field(default=EventType.CONTEXT_DISPOSED, init=False)


@dataclass(frozen=True, kw_only=True)
class AgentStarted(DomainEvent[AgentPayload]):
    event_type: EventType = field(default=EventType.AGENT_STARTED, init=False)


@dataclass(frozen=True, kw_only=True)
class AgentFinished(DomainEvent[AgentPayload]):
    event_type: EventType = field(default=EventType.AGENT_FINISHED, init=False)


@dataclass(frozen=True, kw_only=True)
class SystemError(DomainEvent[SystemErrorPayload]):
    event_type: EventType = field(default=EventType.SYSTEM_ERROR, init=False)
