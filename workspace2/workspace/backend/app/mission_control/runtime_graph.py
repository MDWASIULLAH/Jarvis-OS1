"""A layered map of this JARVIS process, for the Neural Nexus views.

`nexus.py` answers "what is the swarm doing for mission X". This module answers
the other question the UI needs -- "what is this runtime, wired end to end" --
because that is what a neural map of JARVIS actually is: senses, cognition,
routing, the specialist agents, execution, capabilities, memory, and outputs.

Nothing here is decorative. Every node is read off a live object the
composition root already built, and an edge exists only where the runtime
really hands one service to another. Node counts, engine names, capability
enable flags and agent health are the current values, not placeholders, and
`activity` / `last_active` come from the audit log and the mission timeline, so
a node only lights up when something really ran through it.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

#: Depth order of the map. The 3D view turns the index into a Z plane, so this
#: tuple is also the visual front-to-back order.
LAYERS: tuple[tuple[str, str], ...] = (
    ("senses", "Senses"),
    ("cognition", "Cognition"),
    ("routing", "Routing"),
    ("engines", "Engines"),
    ("agents", "Specialist agents"),
    ("execution", "Execution"),
    ("domains", "Capability domains"),
    ("capabilities", "Capabilities"),
    ("memory", "Memory & knowledge"),
    ("outputs", "Outputs"),
)

_LAYER_INDEX = {key: index for index, (key, _) in enumerate(LAYERS)}


class _Graph:
    """Collects nodes and edges, refusing edges to nodes that do not exist."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def node(
        self,
        node_id: str,
        kind: str,
        label: str,
        layer: str,
        *,
        status: str = "ready",
        health: str = "local",
        detail: str = "",
        signals: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if node_id in self._ids:
            return node_id
        self._ids.add(node_id)
        self.nodes.append(
            {
                "node_id": node_id,
                "kind": kind,
                "label": label,
                "layer": _LAYER_INDEX[layer],
                "layer_name": layer,
                "status": status,
                "health": health,
                "detail": detail,
                # Substrings the live event stream is matched against, so the UI
                # can fire the right neuron for a real event.
                "signals": sorted({item.lower() for item in signals if item}),
                "activity": 0,
                "last_active": "",
                "metadata": [{"key": key, "value": str(value)} for key, value in (metadata or {}).items()],
            }
        )
        return node_id

    def edge(self, source: str, target: str, relationship: str, weight: float = 1.0) -> None:
        if source not in self._ids or target not in self._ids or source == target:
            return
        self.edges.append(
            {
                "edge_id": f"{source}->{target}:{relationship}",
                "source_id": source,
                "target_id": target,
                "relationship": relationship,
                "weight": round(weight, 3),
            }
        )


def _senses(graph: _Graph, rt: Any) -> None:
    """Layer 0: the ways a request can actually enter this process."""
    from ..capabilities.vision_ocr import ocr_available

    ocr_ready = ocr_available()
    devices = rt.companions.devices()
    graph.node(
        "sense:text", "sense", "Text prompt", "senses",
        status="online", detail="POST /v1/chat/stream", signals=("chat", "intent"),
        metadata={"endpoint": "/v1/chat/stream", "streaming": True},
    )
    graph.node(
        "sense:attachment", "sense", "Attachments", "senses",
        status="online", detail="Files base64-encoded into the chat request",
        signals=("attachment", "document"), metadata={"max_per_turn": 5},
    )
    graph.node(
        "sense:voice", "sense", "Voice dictation", "senses",
        status="online", detail="Browser speech recognition feeds the same text path",
        signals=("voice", "speech", "stt"),
    )
    graph.node(
        "sense:vision", "sense", "Vision / OCR", "senses",
        status="online" if ocr_ready else "unavailable",
        health="local" if ocr_ready else "degraded",
        detail="POST /v1/vision/ocr" + ("" if ocr_ready else " (no OCR engine installed)"),
        signals=("vision", "ocr", "image"),
    )
    graph.node(
        "sense:companion", "sense", "Paired devices", "senses",
        status="online" if devices else "idle",
        detail=f"{len(devices)} device(s) paired" if devices else "No companion device paired",
        signals=("companion", "device"), metadata={"devices": len(devices)},
    )


def _cognition(graph: _Graph, rt: Any) -> None:
    """Layer 1: the Brain Core pipeline that every request passes through."""
    brain = rt.brain.status()
    intent_model = brain.get("intent_model", {})
    labels = intent_model.get("labels", []) or brain.get("intents_supported", [])
    decision = brain.get("decision_engine", {})

    graph.node(
        "cognition:intent", "cognition", "Intent analyzer", "cognition",
        status="online",
        detail=f"{len(labels)} intents, {'trained model' if intent_model.get('trained') else 'keyword fallback'}",
        signals=("intent", "routing"),
        metadata={
            "intents": len(labels),
            "trained": bool(intent_model.get("trained")),
            "features": intent_model.get("features", 0),
        },
    )
    graph.node(
        "cognition:decision", "cognition", "Decision engine", "cognition",
        status="online",
        detail=f"{decision.get('decisions_made', 0)} decisions, {decision.get('available_tools', 0)} tools registered",
        signals=("decision", "plan"),
        metadata={key: value for key, value in decision.items() if isinstance(value, (int, float, str, bool))},
    )
    graph.node(
        "cognition:reflection", "cognition", "Reflection", "cognition",
        status="online", detail=f"{brain.get('reflection_history', 0)} reflections kept",
        signals=("reflection", "evolution"),
        metadata={"history": brain.get("reflection_history", 0)},
    )

    for sense in ("sense:text", "sense:attachment", "sense:voice", "sense:vision", "sense:companion"):
        graph.edge(sense, "cognition:intent", "feeds", 1.4 if sense == "sense:text" else 0.8)
    graph.edge("cognition:intent", "cognition:decision", "informs", 1.4)


def _routing(graph: _Graph, rt: Any) -> None:
    """Layers 2-3: engine selection, the permission gate, and the engines."""
    status = rt.models.status()
    cloud_ready = bool(status["cloud_configured"] and status["cloud_allowed"])

    graph.node(
        "routing:models", "router", "Model router", "routing",
        status="online",
        detail="auto: deterministic work stays local, generative work goes to the configured engine",
        signals=("model", "router", "generate"),
        metadata={key: value for key, value in status.items() if key != "privacy"},
    )
    graph.node(
        "routing:security", "security", "Permission gate", "routing",
        status="online", detail="Every real-world action needs a confirmed permission",
        signals=("security", "approval", "policy", "permission"),
    )
    graph.node(
        "engine:local", "engine", f"Local engine ({status['local_kind']})", "engines",
        status="online" if status["local_available"] else "offline",
        health="local" if status["local_available"] else "degraded",
        detail="generative" if status["generative_local"] else "deterministic reasoning engine, no free-form writing",
        signals=("local_engine", "local_fallback", str(status["local_kind"])),
        metadata={"kind": status["local_kind"], "generative": status["generative_local"]},
    )
    cloud_model = str(getattr(rt.settings, "cloud_model", "") or "not configured")
    graph.node(
        "engine:cloud", "engine", f"Cloud model ({cloud_model})", "engines",
        status="online" if cloud_ready else "unavailable",
        health="cloud" if cloud_ready else "degraded",
        detail="Used for code and free-form writing while the local engine is deterministic"
        if cloud_ready
        else "No cloud model configured or cloud access is disabled",
        signals=("cloud", "openai_compatible", cloud_model),
        metadata={"model": cloud_model, "configured": status["cloud_configured"], "allowed": status["cloud_allowed"]},
    )

    graph.edge("cognition:decision", "routing:models", "requests", 1.6)
    graph.edge("cognition:decision", "routing:security", "checks", 0.9)
    graph.edge("routing:models", "engine:local", "routes", 1.2)
    graph.edge("routing:models", "engine:cloud", "routes", 1.2 if cloud_ready else 0.3)
    graph.edge("engine:local", "cognition:reflection", "answers", 1.0)
    graph.edge("engine:cloud", "cognition:reflection", "answers", 1.0 if cloud_ready else 0.2)


# BUILDERS_PLACEHOLDER


