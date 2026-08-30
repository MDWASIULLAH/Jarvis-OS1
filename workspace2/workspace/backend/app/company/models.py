"""Immutable organizational contracts for AI Software Company coordination."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class DepartmentKind(str, Enum):
    EXECUTIVE = "executive"; ENGINEERING = "engineering"; INFRASTRUCTURE = "infrastructure"; QUALITY = "quality"; SECURITY = "security"; DOCUMENTATION = "documentation"; DESIGN = "design"; OPERATIONS = "operations"


class CompanyRole(str, Enum):
    CEO = "ceo"; CTO = "cto"; PROJECT_DIRECTOR = "project_director"; SOLUTION_ARCHITECT = "solution_architect"; BACKEND_ENGINEER = "backend_engineer"; FRONTEND_ENGINEER = "frontend_engineer"; MOBILE_ENGINEER = "mobile_engineer"; AI_ML_ENGINEER = "ai_ml_engineer"; DATABASE_ENGINEER = "database_engineer"; API_ENGINEER = "api_engineer"; DEVOPS_ENGINEER = "devops_engineer"; CLOUD_ENGINEER = "cloud_engineer"; PLATFORM_ENGINEER = "platform_engineer"; QA_ENGINEER = "qa_engineer"; TEST_ENGINEER = "test_engineer"; PERFORMANCE_ENGINEER = "performance_engineer"; SECURITY_ENGINEER = "security_engineer"; PRIVACY_ENGINEER = "privacy_engineer"; TECHNICAL_WRITER = "technical_writer"; API_DOCUMENTATION_WRITER = "api_documentation_writer"; UI_DESIGNER = "ui_designer"; UX_DESIGNER = "ux_designer"; RELEASE_MANAGER = "release_manager"; DEPLOYMENT_MANAGER = "deployment_manager"; MONITORING_ENGINEER = "monitoring_engineer"


class ProjectLifecycle(str, Enum):
    CREATED = "created"; ACTIVE = "active"; BLOCKED = "blocked"; COMPLETED = "completed"; ARCHIVED = "archived"


class WorkflowStageKind(str, Enum):
    ARCHITECTURE = "architecture"; IMPLEMENTATION = "implementation"; CODE_REVIEW = "code_review"; TESTING = "testing"; PERFORMANCE_REVIEW = "performance_review"; SECURITY_REVIEW = "security_review"; DOCUMENTATION = "documentation"; RELEASE_REVIEW = "release_review"; DEPLOYMENT_APPROVAL = "deployment_approval"


class GateState(str, Enum): PENDING = "pending"; PASSED = "passed"; FAILED = "failed"
class ReviewKind(str, Enum): PEER = "peer"; ARCHITECTURE = "architecture"; CODE = "code"; DOCUMENTATION = "documentation"; SECURITY = "security"; PERFORMANCE = "performance"


@dataclass(frozen=True)
class Department:
    department_id: str
    project_id: str
    kind: DepartmentKind
    name: str
    roles: tuple[CompanyRole, ...] = ()


@dataclass(frozen=True)
class Milestone:
    milestone_id: str
    title: str
    deadline: datetime | None = None
    completed: bool = False


@dataclass(frozen=True)
class WorkflowStage:
    stage_id: str
    kind: WorkflowStageKind
    required: bool = True
    completed: bool = False


@dataclass(frozen=True)
class QualityGate:
    gate_id: str
    title: str
    state: GateState = GateState.PENDING
    required: bool = True


@dataclass(frozen=True)
class CompanyTask:
    task_id: str
    project_id: str
    title: str
    department_id: str | None = None
    role: CompanyRole | None = None
    dependencies: tuple[str, ...] = ()
    assigned_agent_id: str | None = None
    completed: bool = False


@dataclass(frozen=True)
class ReviewReport:
    review_id: str
    project_id: str
    kind: ReviewKind
    requested_by: str
    reviewer_agent_id: str | None = None
    approved: bool | None = None
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Project:
    project_id: str
    title: str
    goal: str
    lifecycle: ProjectLifecycle = ProjectLifecycle.CREATED
    priority: int = 50
    mission_id: str | None = None
    milestones: tuple[Milestone, ...] = ()
    workflow: tuple[WorkflowStage, ...] = ()
    quality_gates: tuple[QualityGate, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, title: str, goal: str, **values) -> "Project": return cls(str(uuid.uuid4()), title, goal, **values)


@dataclass(frozen=True)
class ProjectDashboard:
    project: Project
    departments: tuple[Department, ...]
    tasks: tuple[CompanyTask, ...]
    reviews: tuple[ReviewReport, ...]
    release_ready: bool
