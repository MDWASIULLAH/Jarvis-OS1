"""Thread-safe mission registry with instance-scoped dependency injection."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .models import Mission, MissionFilter


class MissionDependencies:
    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try: return self._services[name]
        except KeyError as exc: raise LookupError(f"Mission dependency is unavailable: {name}") from exc


class MissionRegistry:
    def __init__(self, dependencies: MissionDependencies | None = None) -> None:
        self._dependencies = dependencies or MissionDependencies()
        self._missions: dict[str, Mission] = {}
        self._history: dict[str, list[Mission]] = {}
        self._factories: dict[str, Callable[[str, str, MissionDependencies], Mission]] = {}
        self._lock = threading.RLock()

    def register(self, mission: Mission) -> Mission:
        with self._lock:
            if mission.mission_id in self._missions: raise ValueError(f"Mission already registered: {mission.mission_id}")
            self._missions[mission.mission_id] = mission
            self._history[mission.mission_id] = [mission]
        return mission

    def register_factory(self, name: str, factory: Callable[[str, str, MissionDependencies], Mission]) -> None:
        with self._lock:
            if not name or name in self._factories:
                raise ValueError(f"Mission factory is already registered: {name}")
            self._factories[name] = factory

    def create(self, factory_name: str, title: str, description: str) -> Mission:
        with self._lock:
            try: factory = self._factories[factory_name]
            except KeyError as exc: raise KeyError(f"Unknown mission factory: {factory_name}") from exc
        return self.register(factory(title, description, self._dependencies))

    def get(self, mission_id: str) -> Mission:
        with self._lock:
            try: return self._missions[mission_id]
            except KeyError as exc: raise KeyError(f"Unknown mission: {mission_id}") from exc

    def update(self, mission: Mission, *, expected_version: int | None = None) -> Mission:
        with self._lock:
            current = self.get(mission.mission_id)
            if expected_version is not None and current.version != expected_version: raise ValueError(f"Stale mission version: {mission.mission_id}")
            updated = replace(mission, version=current.version + 1, updated_at=datetime.now(timezone.utc))
            self._missions[mission.mission_id] = updated
            self._history[mission.mission_id].append(updated)
            return updated

    def find(self, query: MissionFilter = MissionFilter()) -> tuple[Mission, ...]:
        with self._lock: missions = tuple(self._missions.values())
        text = query.text.lower()
        return tuple(sorted((item for item in missions if (query.lifecycle is None or item.lifecycle is query.lifecycle) and (not text or text in item.title.lower() or text in item.description.lower())), key=lambda item: item.created_at))

    def history(self, mission_id: str) -> tuple[Mission, ...]:
        with self._lock: return tuple(self._history.get(mission_id, ()))
