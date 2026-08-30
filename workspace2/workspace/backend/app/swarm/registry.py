"""Thread-safe agent registry with pluggable factories and lazy construction."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from .models import AgentKind, AgentLifecycle, SwarmAgent


class AgentDependencies:
    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Swarm dependency is unavailable: {name}") from exc


AgentFactory = Callable[[AgentKind, str, AgentDependencies], SwarmAgent]


class AgentRegistry:
    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        self._dependencies = dependencies or AgentDependencies()
        self._agents: dict[str, SwarmAgent] = {}
        self._factories: dict[AgentKind, AgentFactory] = {}
        self._lock = threading.RLock()

    def register_factory(self, kind: AgentKind, factory: AgentFactory) -> None:
        with self._lock:
            if kind in self._factories:
                raise ValueError(f"Agent factory is already registered: {kind.value}")
            self._factories[kind] = factory

    def create(self, kind: AgentKind, name: str, *, parent_agent_id: str | None = None, context_id: str | None = None) -> SwarmAgent:
        with self._lock:
            factory = self._factories.get(kind, self._default_factory)
        agent = factory(kind, name, self._dependencies)
        agent = replace(agent, parent_agent_id=parent_agent_id, context_id=context_id, lifecycle=AgentLifecycle.READY)
        return self.register(agent)

    def register(self, agent: SwarmAgent) -> SwarmAgent:
        with self._lock:
            if agent.agent_id in self._agents:
                raise ValueError(f"Agent is already registered: {agent.agent_id}")
            self._agents[agent.agent_id] = agent
        return agent

    def discover(self, *, kind: AgentKind | None = None, lifecycle: AgentLifecycle | None = None) -> tuple[SwarmAgent, ...]:
        with self._lock:
            items = tuple(self._agents.values())
        return tuple(sorted((item for item in items if (kind is None or item.kind is kind) and (lifecycle is None or item.lifecycle is lifecycle)), key=lambda item: item.agent_id))

    def get(self, agent_id: str) -> SwarmAgent:
        with self._lock:
            try:
                return self._agents[agent_id]
            except KeyError as exc:
                raise KeyError(f"Unknown swarm agent: {agent_id}") from exc

    def update(self, agent: SwarmAgent, *, expected_version: int | None = None) -> SwarmAgent:
        with self._lock:
            current = self.get(agent.agent_id)
            if expected_version is not None and current.version != expected_version:
                raise ValueError(f"Stale agent version: {agent.agent_id}")
            replacement = replace(agent, version=current.version + 1)
            self._agents[agent.agent_id] = replacement
            return replacement

    def remove(self, agent_id: str) -> SwarmAgent:
        with self._lock:
            try:
                return self._agents.pop(agent_id)
            except KeyError as exc:
                raise KeyError(f"Unknown swarm agent: {agent_id}") from exc

    @staticmethod
    def _default_factory(kind: AgentKind, name: str, dependencies: AgentDependencies) -> SwarmAgent:
        del dependencies
        return SwarmAgent(str(uuid.uuid4()), kind, name, lifecycle=AgentLifecycle.INITIALIZING)
