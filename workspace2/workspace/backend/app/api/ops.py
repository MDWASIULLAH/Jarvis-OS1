"""
api/ops.py

HTTP surface for the operations tier: Mission Control, the AI Workforce
(swarm), the AI Software Company (Development Studio), the knowledge graph, and
the Security Framework.

Every manager behind these routes was already implemented and tested; none of
them had an HTTP surface, which is the entire reason those dashboards rendered
"Unavailable" or "API is not exposed by this deployment". This module only
adapts existing managers -- it contains no business logic of its own.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..company.models import CompanyRole, DepartmentKind, ReviewKind
from ..core.runtime import runtime
from ..knowledge.graph_models import (
    EntityType, GraphAttribute, GraphEdge, GraphNode, GraphQuery, GraphTraversal,
    RelationshipType, TraversalDirection,
)
from ..mission_control.models import MissionFilter, MissionLifecycle
from ..security_framework.models import Permission, PolicyDomain, SecurityAction
from ..swarm.models import AgentKind, SwarmTask

router = APIRouter(prefix="/v1", tags=["JARVIS Operations"])


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def encode(value: Any) -> Any:
    """Serialize frozen dataclasses, enums, and datetimes the managers return."""
    return jsonable_encoder(value)


def _enum(enum_type: Any, value: str, label: str) -> Any:
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise HTTPException(status_code=422, detail=f"Unknown {label}: {value}. Allowed: {allowed}") from exc


def _missing(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc).strip("'\""))


def _conflict(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def _timeline_events(entries: Any) -> list[dict[str, Any]]:
    """Map TimelineEntry records onto the MissionEvent shape the UI reads."""
    return [
        {
            "event_id": f"{entry.mission_id}:{entry.sequence}",
            "sequence": entry.sequence,
            "event_type": entry.event_type,
            "timestamp": entry.timestamp.isoformat(),
            "source": entry.source,
            "detail": entry.detail,
            "metadata": {"correlation_id": entry.correlation_id},
        }
        for entry in entries
    ]


# --------------------------------------------------------------------------- #
# Mission Control
# --------------------------------------------------------------------------- #

class MissionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)


class MissionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    lifecycle: Optional[str] = Field(default=None, max_length=40)


@router.get("/missions")
def list_missions(lifecycle: str = "", text: str = "") -> list[dict[str, Any]]:
    query = MissionFilter(
        lifecycle=_enum(MissionLifecycle, lifecycle, "mission lifecycle") if lifecycle else None,
        text=text,
    )
    return encode(runtime.missions.find_missions(query))


@router.post("/missions", status_code=201)
def create_mission(request: MissionCreateRequest) -> dict[str, Any]:
    return encode(runtime.missions.create_mission(request.title, request.description))


@router.get("/missions/{mission_id}")
def mission_detail(mission_id: str) -> dict[str, Any]:
    manager = runtime.missions
    try:
        mission = manager.registry.get(mission_id)
    except KeyError as exc:
        raise _missing(exc) from exc
    inspections = manager.inspect_mission(mission_id)
    return {
        **encode(mission),
        "timeline": _timeline_events(manager.timeline(mission_id)),
        "flight_records": _timeline_events(record.timeline_entry for record in manager.flight_records(mission_id)),
        "metrics": encode(manager.metrics(mission_id)),
        "resources": encode(manager.resource_snapshot()),
        "related_agents": [item.agent_id for item in inspections],
        "agents": encode(inspections),
    }


@router.patch("/missions/{mission_id}")
def update_mission(mission_id: str, request: MissionUpdateRequest) -> dict[str, Any]:
    lifecycle = _enum(MissionLifecycle, request.lifecycle, "mission lifecycle") if request.lifecycle else None
    try:
        return encode(runtime.missions.update_mission(mission_id, title=request.title, description=request.description, lifecycle=lifecycle))
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.post("/missions/{mission_id}/{action}")
def mission_action(mission_id: str, action: str) -> dict[str, Any]:
    manager = runtime.missions
    transitions = {
        "pause": manager.pause_mission,
        "resume": manager.resume_mission,
        "complete": manager.complete_mission,
        "cancel": manager.cancel_mission,
        "archive": manager.archive_mission,
    }
    if action not in transitions:
        raise HTTPException(status_code=404, detail=f"Unknown mission action: {action}. Allowed: {', '.join(transitions)}")
    try:
        return encode(transitions[action](mission_id))
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.get("/missions/{mission_id}/nexus")
def mission_nexus(mission_id: str) -> dict[str, Any]:
    try:
        return encode(runtime.missions.graph_snapshot(mission_id))
    except KeyError as exc:
        raise _missing(exc) from exc


@router.get("/missions/{mission_id}/nexus/snapshots")
def mission_nexus_snapshots(mission_id: str) -> list[dict[str, Any]]:
    manager = runtime.missions
    try:
        manager.registry.get(mission_id)
    except KeyError as exc:
        raise _missing(exc) from exc
    snapshots = manager.nexus.snapshots(mission_id)
    # Build one on demand so the history view is never empty for a live mission.
    return encode(snapshots or (manager.graph_snapshot(mission_id),))


@router.get("/missions/{mission_id}/replay")
def mission_replay(mission_id: str) -> dict[str, Any]:
    try:
        replay = runtime.missions.replay_mission(mission_id)
    except KeyError as exc:
        raise _missing(exc) from exc
    return {"mission_id": replay.mission_id, "timeline": _timeline_events(replay.timeline), "snapshots": encode(replay.snapshots)}


# --------------------------------------------------------------------------- #
# AI Workforce (swarm)
# --------------------------------------------------------------------------- #

class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="worker", max_length=40)
    parent_agent_id: Optional[str] = Field(default=None, max_length=100)


class TaskAssignRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    priority: int = Field(default=50, ge=0, le=100)
    agent_id: Optional[str] = Field(default=None, max_length=100)
    mission_id: Optional[str] = Field(default=None, max_length=100)


class BroadcastRequest(BaseModel):
    sender_agent_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5000)


def _agent_payload(agent: Any) -> dict[str, Any]:
    briefs = getattr(runtime.get(), "_agent_briefs", {})
    assignments = runtime.swarm.__dict__.get("_assignments", {})
    current = next((task_id for task_id, item in assignments.items() if item.agent_id == agent.agent_id), None)
    payload = encode(agent)
    payload["current_task"] = current
    payload["brief"] = briefs.get(agent.agent_id, "")
    payload["mission_id"] = runtime.SYSTEM_MISSION_ID
    return payload


@router.get("/workforce/agents")
def list_workforce_agents(kind: str = "") -> list[dict[str, Any]]:
    selected = _enum(AgentKind, kind, "agent kind") if kind else None
    return [_agent_payload(agent) for agent in runtime.swarm.registry.discover(kind=selected)]


@router.post("/workforce/agents", status_code=201)
def create_workforce_agent(request: AgentCreateRequest) -> dict[str, Any]:
    kind = _enum(AgentKind, request.kind, "agent kind")
    try:
        return _agent_payload(runtime.swarm.create_agent(kind, request.name, parent_agent_id=request.parent_agent_id))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/workforce/communications")
def workforce_communications(text: str = "") -> list[dict[str, Any]]:
    messages = runtime.swarm.__dict__.get("_messages", [])
    lowered = text.lower()
    return encode([item for item in messages if not lowered or lowered in item.content.lower()])


@router.get("/workforce/status")
def workforce_status() -> dict[str, Any]:
    swarm = runtime.swarm
    agents = swarm.registry.discover()
    tasks = swarm.__dict__.get("_tasks", {})
    by_lifecycle: dict[str, int] = {}
    for agent in agents:
        by_lifecycle[agent.lifecycle.value] = by_lifecycle.get(agent.lifecycle.value, 0) + 1
    return {
        "total_agents": len(agents),
        "executive_agents": sum(agent.kind is AgentKind.EXECUTIVE for agent in agents),
        "worker_agents": sum(agent.kind is AgentKind.WORKER for agent in agents),
        "helper_agents": sum(agent.kind is AgentKind.HELPER for agent in agents),
        "open_tasks": len(tasks),
        "messages": len(swarm.__dict__.get("_messages", [])),
        "recoveries": len(swarm.__dict__.get("_recoveries", [])),
        "planner_available": swarm.planner_available,
        "executor_available": swarm.executor_available,
        "lifecycle_breakdown": by_lifecycle,
        "average_health": round(sum(agent.health.score for agent in agents) / len(agents), 3) if agents else 0.0,
    }


@router.get("/workforce/tasks")
def workforce_tasks() -> list[dict[str, Any]]:
    return encode(list(runtime.swarm.__dict__.get("_tasks", {}).values()))


@router.post("/workforce/tasks", status_code=201)
def assign_workforce_task(request: TaskAssignRequest) -> dict[str, Any]:
    swarm = runtime.swarm
    task = SwarmTask(str(uuid.uuid4()), request.title, request.description, priority=request.priority)
    try:
        assignment = swarm.assign_task(task, agent_id=request.agent_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime.missions.record_task(request.mission_id or runtime.SYSTEM_MISSION_ID, task, assignment.agent_id)
    return {"task": encode(task), "assignment": encode(assignment)}


@router.get("/workforce/agents/{agent_id}")
def workforce_agent(agent_id: str) -> dict[str, Any]:
    try:
        return _agent_payload(runtime.swarm.registry.get(agent_id))
    except KeyError as exc:
        raise _missing(exc) from exc


@router.delete("/workforce/agents/{agent_id}")
def destroy_workforce_agent(agent_id: str) -> dict[str, Any]:
    try:
        return encode(runtime.swarm.destroy_agent(agent_id))
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.post("/workforce/agents/{agent_id}/{action}")
def workforce_agent_action(agent_id: str, action: str) -> dict[str, Any]:
    swarm = runtime.swarm
    transitions = {
        "pause": lambda: swarm.pause_agent(agent_id),
        "resume": lambda: swarm.resume_agent(agent_id),
        "cancel": lambda: swarm.cancel_agent(agent_id),
        "recover": lambda: swarm.recover_agent(agent_id, "Manual recovery requested from the Workforce dashboard."),
        "health-check": lambda: swarm.health_check(agent_id),
    }
    if action not in transitions:
        raise HTTPException(status_code=404, detail=f"Unknown agent action: {action}. Allowed: {', '.join(transitions)}")
    try:
        return _agent_payload(transitions[action]())
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.post("/workforce/broadcast")
def workforce_broadcast(request: BroadcastRequest) -> list[dict[str, Any]]:
    try:
        messages = runtime.swarm.broadcast(request.sender_agent_id, request.content, str(uuid.uuid4()))
    except KeyError as exc:
        raise _missing(exc) from exc
    for message in messages:
        runtime.missions.record_communication(runtime.SYSTEM_MISSION_ID, message)
    return encode(messages)


# --------------------------------------------------------------------------- #
# AI Software Company (Development Studio)
# --------------------------------------------------------------------------- #

class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    goal: str = Field(min_length=1, max_length=5000)
    priority: int = Field(default=50, ge=0, le=100)


class DepartmentCreateRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=60)
    name: Optional[str] = Field(default=None, max_length=200)
    roles: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    kind: str = Field(default="code", max_length=40)
    requested_by: str = Field(default="operator", max_length=200)


@router.get("/company/projects")
def list_projects() -> list[dict[str, Any]]:
    return encode(runtime.company.registry.discover())


@router.post("/company/projects", status_code=201)
def create_project(request: ProjectCreateRequest) -> dict[str, Any]:
    return encode(runtime.company.create_project(request.title, request.goal, priority=request.priority))


@router.get("/company/projects/{project_id}")
def project_dashboard(project_id: str) -> dict[str, Any]:
    company = runtime.company
    try:
        dashboard = company.dashboard(project_id)
    except KeyError as exc:
        raise _missing(exc) from exc
    return {**encode(dashboard), "progress": company.track_progress(project_id)}


@router.post("/company/projects/{project_id}/departments", status_code=201)
def create_department(project_id: str, request: DepartmentCreateRequest) -> dict[str, Any]:
    company = runtime.company
    kind = _enum(DepartmentKind, request.kind, "department kind")
    try:
        department = company.create_department(project_id, kind, request.name)
    except KeyError as exc:
        raise _missing(exc) from exc
    if request.roles:
        roles = tuple(_enum(CompanyRole, role, "company role") for role in request.roles)
        department = company.assign_roles(department.department_id, roles)
    return encode(department)


@router.post("/company/projects/{project_id}/reviews", status_code=201)
def request_review(project_id: str, request: ReviewRequest) -> dict[str, Any]:
    kind = _enum(ReviewKind, request.kind, "review kind")
    try:
        return encode(runtime.company.request_review(project_id, kind, request.requested_by))
    except KeyError as exc:
        raise _missing(exc) from exc


@router.get("/company/tasks")
def company_tasks() -> list[dict[str, Any]]:
    return encode(list(runtime.company.__dict__.get("_tasks", {}).values()))


@router.get("/company/departments")
def company_departments() -> list[dict[str, Any]]:
    return encode(list(runtime.company.__dict__.get("_departments", {}).values()))


@router.get("/company/roles")
def company_roles() -> dict[str, list[str]]:
    """The role and department vocabulary the Development Studio can offer."""
    return {
        "roles": [role.value for role in CompanyRole],
        "departments": [kind.value for kind in DepartmentKind],
        "reviews": [kind.value for kind in ReviewKind],
    }


# --------------------------------------------------------------------------- #
# Knowledge graph
# --------------------------------------------------------------------------- #

class GraphNodeRequest(BaseModel):
    label: str = Field(min_length=1, max_length=300)
    entity_type: str = Field(default="generic", max_length=60)
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class GraphEdgeRequest(BaseModel):
    source_node_id: str = Field(min_length=1, max_length=200)
    target_node_id: str = Field(min_length=1, max_length=200)
    relationship: str = Field(default="related_to", max_length=60)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


@router.get("/graph")
def graph_overview(limit: int = Query(default=250, ge=1, le=2000), label: str = "", entity_type: str = "") -> dict[str, Any]:
    graph = runtime.graph
    query = GraphQuery(
        entity_types=(_enum(EntityType, entity_type, "entity type"),) if entity_type else (),
        label_contains=label or None,
        limit=limit,
    )
    result = graph.query(query)
    return {
        "nodes": encode(result.nodes),
        "edges": encode(result.edges),
        "total_nodes": len(result.nodes),
        "total_edges": len(result.edges),
        "entity_types": [item.value for item in EntityType],
        "relationships": [item.value for item in RelationshipType],
    }


@router.post("/graph/nodes", status_code=201)
def create_graph_node(request: GraphNodeRequest) -> dict[str, Any]:
    node = GraphNode(
        node_id=str(uuid.uuid4()),
        entity_type=_enum(EntityType, request.entity_type, "entity type"),
        label=request.label,
        attributes=tuple(GraphAttribute(key, value) for key, value in request.attributes.items()),
        tags=tuple(request.tags),
        importance=request.importance,
        confidence=request.confidence,
    )
    try:
        return encode(runtime.graph.create_node(node))
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.post("/graph/edges", status_code=201)
def create_graph_edge(request: GraphEdgeRequest) -> dict[str, Any]:
    edge = GraphEdge(
        edge_id=str(uuid.uuid4()),
        source_node_id=request.source_node_id,
        target_node_id=request.target_node_id,
        relationship=_enum(RelationshipType, request.relationship, "relationship"),
        weight=request.weight,
    )
    try:
        return encode(runtime.graph.create_edge(edge))
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.get("/graph/nodes/{node_id}")
def graph_node(node_id: str) -> dict[str, Any]:
    graph = runtime.graph
    try:
        node = graph.node(node_id)
    except KeyError as exc:
        raise _missing(exc) from exc
    outbound, inbound = graph.neighbors(node_id, direction=TraversalDirection.OUTBOUND), graph.neighbors(node_id, direction=TraversalDirection.INBOUND)
    return {
        "node": encode(node),
        "outbound": encode(outbound),
        "inbound": encode(inbound),
        "similar": [{"node": encode(item), "similarity": score} for item, score in graph.similar_nodes(node_id, limit=8)],
    }


@router.get("/graph/traverse/{node_id}")
def graph_traverse(node_id: str, depth: int = Query(default=2, ge=1, le=6), direction: str = "both") -> dict[str, Any]:
    traversal = GraphTraversal(
        start_node_id=node_id,
        max_depth=depth,
        direction=_enum(TraversalDirection, direction, "traversal direction"),
    )
    try:
        subgraph = runtime.graph.traverse(traversal)
    except KeyError as exc:
        raise _missing(exc) from exc
    return {"nodes": encode(subgraph.nodes), "edges": encode(subgraph.edges)}


@router.delete("/graph/nodes/{node_id}")
def delete_graph_node(node_id: str) -> dict[str, Any]:
    try:
        return encode(runtime.graph.delete_node(node_id))
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


# --------------------------------------------------------------------------- #
# Security Framework
# --------------------------------------------------------------------------- #

class SecurityEvaluateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    target: str = Field(default="", max_length=1000)
    domain: str = Field(default="filesystem", max_length=60)
    permissions: list[str] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    granted: bool
    decided_by: str = Field(default="operator", max_length=200)


class TrustRequest(BaseModel):
    subject_id: str = Field(min_length=1, max_length=200)
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=1000)


def _security_action(request: SecurityEvaluateRequest) -> SecurityAction:
    return SecurityAction(
        str(uuid.uuid4()),
        request.title,
        tuple(_enum(Permission, item, "permission") for item in request.permissions),
        _enum(PolicyDomain, request.domain, "policy domain"),
        target=request.target,
    )


@router.get("/security/overview")
def security_overview() -> dict[str, Any]:
    manager = runtime.security_framework
    registry = manager.registry
    with registry._lock:  # noqa: SLF001 - the registry exposes no read-only accessor yet.
        policies = list(registry._policies.values())
        approvals = list(registry._approvals.values())
        incidents = list(registry._incidents.values())
        trust = list(registry._trust.values())
        quarantine = sorted(registry._quarantine)
    audits = manager.audit_history()
    return {
        "policies": encode(policies),
        "approvals": encode(approvals),
        "incidents": encode(incidents),
        "trust_scores": encode(trust),
        "quarantined": quarantine,
        "audit_records": encode(audits[-100:]),
        "counts": {
            "policies": len(policies),
            "pending_approvals": sum(item.state.value == "pending" for item in approvals),
            "incidents": len(incidents),
            "audit_records": len(audits),
        },
        "vocabulary": {
            "domains": [item.value for item in PolicyDomain],
            "permissions": [item.value for item in Permission],
        },
    }


@router.post("/security/evaluate")
def security_evaluate(request: SecurityEvaluateRequest) -> dict[str, Any]:
    manager = runtime.security_framework
    action = _security_action(request)
    report = manager.evaluate(action)
    return {"action": encode(action), "report": encode(report), "threats": encode(manager.detect_threats(action))}


@router.post("/security/approvals", status_code=201)
def security_request_approval(request: SecurityEvaluateRequest) -> dict[str, Any]:
    manager = runtime.security_framework
    action = _security_action(request)
    return {"action": encode(action), "approval": encode(manager.request_approval(action, "operator"))}


@router.post("/security/approvals/{approval_id}/decide")
def security_decide_approval(approval_id: str, request: ApprovalDecisionRequest) -> dict[str, Any]:
    try:
        return encode(runtime.security_framework.decide_approval(approval_id, granted=request.granted, decided_by=request.decided_by))
    except KeyError as exc:
        raise _missing(exc) from exc
    except ValueError as exc:
        raise _conflict(exc) from exc


@router.get("/security/audit")
def security_audit(text: str = "") -> list[dict[str, Any]]:
    return encode(runtime.security_framework.audit_history(text))


@router.post("/security/trust")
def security_set_trust(request: TrustRequest) -> dict[str, Any]:
    return encode(runtime.security_framework.set_trust(request.subject_id, request.score, request.rationale))


# --------------------------------------------------------------------------- #
# Subsystem diagnostics
# --------------------------------------------------------------------------- #

# Each probe returns the one fact that proves the subsystem is really wired up.
# A probe that raises is reported as "offline" with the exception text rather
# than failing the whole response -- a single broken manager must not blank the
# other twenty-three.
def _probe_runtime() -> str:
    data_dir = runtime.settings.data_dir
    return f"Composition root live, data dir {data_dir}"


def _probe_events() -> str:
    return f"{runtime.events.subscriber_count()} subscribers, {len(runtime.events.traces())} traces recorded"


def _probe_models() -> tuple[str, str]:
    status = runtime.models.status()
    local = bool(status.get("local_available"))
    generative = bool(status.get("generative_local"))
    cloud = bool(status.get("cloud_configured") and status.get("cloud_allowed"))
    detail = f"Default {status.get('default', 'local')}, local engine {status.get('local_kind', 'unknown')}"
    if generative or cloud:
        return "healthy", f"{detail}, generative routing available"
    if local:
        return "degraded", f"{detail}, retrieval only -- no generative model configured"
    return "offline", f"{detail}, no model reachable"


def _probe_intent() -> tuple[str, str]:
    intent = runtime.brain.status().get("intent_model", {})
    labels = intent.get("label_count", 0)
    if intent.get("trained"):
        return "healthy", f"Classifier trained on {labels} intents"
    return "degraded", f"Classifier untrained ({labels} intents registered)"


def _probe_decision_engine() -> str:
    return f"{len(runtime.brain.decision_engine.get_history(1000))} decisions recorded"


def _probe_reflection() -> str:
    history = getattr(runtime.brain, "_reflect_history", [])
    return f"{len(history)} reflection cycles recorded"


def _probe_planner() -> str:
    return f"{type(runtime.planner).__name__} ready, {type(runtime.executor).__name__} attached"


def _probe_capabilities() -> tuple[str, str]:
    reports = runtime.capabilities.health_snapshot()
    total = len(runtime.capabilities.registered_names())
    healthy = sum(1 for report in reports.values() if getattr(report.status, "value", report.status) == "healthy")
    detail = f"{healthy}/{total} capabilities healthy"
    if not total:
        return "offline", "No capabilities registered"
    return ("healthy" if healthy == total else "degraded"), detail


def _probe_short_term() -> str:
    return f"{len(runtime.memory.short_term.recent())} entries in the working set"


def _probe_long_term() -> str:
    return f"{len(runtime.memory.long_term.all_facts())} facts, {runtime.memory.summaries.count()} summaries"


def _probe_memory_fabric() -> str:
    from ..memory_fabric.models import MemoryQuery

    matches = runtime.memory_fabric.search(MemoryQuery(limit=1000)).matches
    return f"{len(matches)} managed memories indexed"


def _probe_knowledge() -> str:
    return f"{len(runtime.knowledge.documents())} documents ingested"


def _probe_graph() -> str:
    result = runtime.graph.query(GraphQuery(limit=2000))
    return f"{len(result.nodes)} entities, {len(result.edges)} relationships"


def _probe_swarm() -> tuple[str, str]:
    agents = runtime.swarm.monitor_agents()
    ready = sum(1 for agent in agents if getattr(agent.lifecycle, "value", agent.lifecycle) in {"ready", "busy"})
    if not agents:
        return "offline", "No agents registered"
    return ("healthy" if ready else "degraded"), f"{ready}/{len(agents)} agents ready"


def _probe_missions() -> str:
    missions = runtime.missions.find_missions(MissionFilter())
    metrics = runtime.missions.metrics(runtime.SYSTEM_MISSION_ID)
    return f"{len(missions)} missions, {metrics.active_agents} active agents"


def _probe_company() -> str:
    projects = runtime.company.registry.discover()
    return f"{len(projects)} software projects tracked"


def _probe_security() -> str:
    registry = runtime.security_framework.registry
    with registry._lock:  # noqa: SLF001 - the registry exposes no read-only accessor yet.
        policies = len(registry._policies)
    return f"{policies} policies, {len(runtime.security_framework.audit_history())} audit records"


def _probe_audit() -> str:
    return f"{len(runtime.audit.recent(1000))} audit entries retained"


def _probe_tasks() -> str:
    return f"{len(runtime.tasks.list())} tasks stored"


def _probe_goals() -> str:
    summary = runtime.goals.status_summary()
    return f"{summary.get('total_goals', 0)} goals, {summary.get('active_count', 0)} active"


def _probe_plugins() -> tuple[str, str]:
    plugins = runtime.plugins.available()
    if not plugins:
        return "degraded", "No plugins discovered"
    return "healthy", f"{len(plugins)} plugins discovered"


def _probe_connectors() -> tuple[str, str]:
    statuses = runtime.connectors.status_all()
    connected = sum(1 for item in statuses if item.get("connected"))
    detail = f"{connected}/{len(statuses)} connectors configured"
    return ("healthy" if connected else "degraded"), detail


def _probe_system_monitor() -> str:
    snapshot = runtime.system_monitor.snapshot(runtime.settings.data_dir)
    memory = snapshot.get("memory") or {}
    return f"CPU {snapshot.get('cpu_percent', 0)}%, memory {memory.get('percent', 0)}%"


# (component, tier, probe). A probe returning a bare string means "healthy".
_DIAGNOSTIC_PROBES: tuple[tuple[str, str, Any], ...] = (
    ("Runtime", "core", _probe_runtime),
    ("Event Bus", "core", _probe_events),
    ("System Monitor", "core", _probe_system_monitor),
    ("Audit Log", "core", _probe_audit),
    ("Model Router", "cognition", _probe_models),
    ("Intent Classifier", "cognition", _probe_intent),
    ("Decision Engine", "cognition", _probe_decision_engine),
    ("Reflection", "cognition", _probe_reflection),
    ("Planner", "cognition", _probe_planner),
    ("Capability Registry", "cognition", _probe_capabilities),
    ("Short-term Memory", "memory", _probe_short_term),
    ("Long-term Memory", "memory", _probe_long_term),
    ("Memory Fabric", "memory", _probe_memory_fabric),
    ("Knowledge Base", "memory", _probe_knowledge),
    ("Knowledge Graph", "memory", _probe_graph),
    ("Mission Control", "operations", _probe_missions),
    ("Agent Swarm", "operations", _probe_swarm),
    ("Software Company", "operations", _probe_company),
    ("Security Framework", "operations", _probe_security),
    ("Task Store", "platform", _probe_tasks),
    ("Goals", "platform", _probe_goals),
    ("Plugins", "platform", _probe_plugins),
    ("Connectors", "platform", _probe_connectors),
)


@router.get("/system/diagnostics")
def system_diagnostics() -> dict[str, Any]:
    """Live per-subsystem health, measured by calling each manager.

    The Operations Center used to hardcode `available: false` for most of this
    list, which reported subsystems as dead while they were serving traffic.
    Every row below is now the result of a real call against the running
    Runtime, so an "offline" row means something is genuinely broken.
    """
    components: list[dict[str, str]] = []
    for name, tier, probe in _DIAGNOSTIC_PROBES:
        try:
            outcome = probe()
            status, detail = outcome if isinstance(outcome, tuple) else ("healthy", outcome)
        except Exception as exc:  # noqa: BLE001 - one dead manager must not blank the rest.
            status, detail = "offline", f"{type(exc).__name__}: {exc}"
        components.append({"component": name, "tier": tier, "status": status, "detail": detail})

    counts = {"healthy": 0, "degraded": 0, "offline": 0}
    for item in components:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    overall = "healthy" if not counts["offline"] and not counts["degraded"] else ("degraded" if not counts["offline"] else "offline")
    return {
        "components": components,
        "counts": counts,
        "total": len(components),
        "overall": overall,
        "tiers": ["core", "cognition", "memory", "operations", "platform"],
    }


# --------------------------------------------------------------------------- #
# Live event stream
# --------------------------------------------------------------------------- #

@router.get("/events/stream")
async def events_stream() -> StreamingResponse:
    """Server-sent events for panels that refresh on real runtime activity.

    Backed by the mission timeline rather than a second subscription, so the
    stream reports exactly what Mission Control recorded.
    """
    manager = runtime.missions
    mission_id = runtime.SYSTEM_MISSION_ID

    async def publish():
        seen = len(manager.timeline(mission_id))
        yield "event: ready\ndata: {}\n\n"
        idle = 0
        while idle < 3600:
            entries = manager.timeline(mission_id)
            if len(entries) > seen:
                for entry in entries[seen:]:
                    payload = {
                        "type": entry.event_type,
                        "payload": {
                            "source": entry.source,
                            "detail": entry.detail,
                            "status": entry.event_type.rsplit(".", 1)[-1],
                            "timestamp": entry.timestamp.isoformat(),
                        },
                    }
                    yield f"event: message\ndata: {json.dumps(payload)}\n\n"
                seen = len(entries)
                idle = 0
            else:
                idle += 1
                if idle % 20 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        publish(),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache, no-transform", "x-accel-buffering": "no"},
    )
