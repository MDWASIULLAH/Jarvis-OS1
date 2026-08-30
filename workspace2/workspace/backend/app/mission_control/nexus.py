"""Backend-only live workforce graph snapshots for future visualization clients."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace

from .models import NexusEdge, NexusFilter, NexusNode, NexusNodeKind, NexusRelationship, NexusSnapshot


class NeuralNexus:
    def __init__(self) -> None:
        self._snapshots: dict[str, list[NexusSnapshot]] = {}
        self._lock = threading.RLock()

    def build(self, mission_id: str, mission_title: str, agents: tuple[object, ...], task_ids: tuple[str, ...] = ()) -> NexusSnapshot:
        nodes = [NexusNode(mission_id, NexusNodeKind.MISSION, mission_title)]
        edges = []
        kind_map = {"executive": NexusNodeKind.EXECUTIVE_AGENT, "department_manager": NexusNodeKind.DEPARTMENT_MANAGER, "worker": NexusNodeKind.WORKER_AGENT, "helper": NexusNodeKind.HELPER_AGENT}
        for agent in agents:
            agent_id, kind, name = getattr(agent, "agent_id"), getattr(agent, "kind"), getattr(agent, "name")
            nodes.append(NexusNode(agent_id, kind_map.get(getattr(kind, "value", ""), NexusNodeKind.WORKER_AGENT), name))
            parent = getattr(agent, "parent_agent_id", None)
            edges.append(NexusEdge(str(uuid.uuid4()), parent or mission_id, agent_id, NexusRelationship.CHILD if parent else NexusRelationship.CREATED))
        for task_id in task_ids:
            nodes.append(NexusNode(task_id, NexusNodeKind.TASK, task_id))
            edges.append(NexusEdge(str(uuid.uuid4()), mission_id, task_id, NexusRelationship.CREATED))
        snapshot = NexusSnapshot(str(uuid.uuid4()), mission_id, tuple(nodes), tuple(edges))
        with self._lock: self._snapshots.setdefault(mission_id, []).append(snapshot)
        return snapshot

    def snapshots(self, mission_id: str) -> tuple[NexusSnapshot, ...]:
        with self._lock: return tuple(self._snapshots.get(mission_id, ()))

    def filter(self, snapshot: NexusSnapshot, query: NexusFilter) -> NexusSnapshot:
        text = query.text.lower()
        nodes = tuple(item for item in snapshot.nodes if (not query.kinds or item.kind in query.kinds) and (not text or text in item.label.lower()))
        selected = {item.node_id for item in nodes}
        return replace(snapshot, nodes=nodes, edges=tuple(edge for edge in snapshot.edges if edge.source_id in selected and edge.target_id in selected))

    def expand(self, snapshot: NexusSnapshot, node_id: str) -> tuple[NexusNode, ...]:
        neighboring = {edge.target_id for edge in snapshot.edges if edge.source_id == node_id} | {edge.source_id for edge in snapshot.edges if edge.target_id == node_id}
        return tuple(node for node in snapshot.nodes if node.node_id in neighboring)

    def collapse(self, snapshot: NexusSnapshot, node_id: str) -> NexusSnapshot:
        return replace(snapshot, nodes=tuple(node for node in snapshot.nodes if node.node_id != node_id), edges=tuple(edge for edge in snapshot.edges if node_id not in (edge.source_id, edge.target_id)))
