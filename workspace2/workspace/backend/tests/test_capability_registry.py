from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.capabilities.builtins import build_builtin_registry
from app.capabilities.contracts import (
    CapabilityContext,
    CapabilityMetadata,
    CapabilityRequest,
    CapabilityResult,
    HealthReport,
    HealthStatus,
    ValidationResult,
)
from app.capabilities.registry import CapabilityRegistry


@dataclass
class ProbeCapability:
    metadata: CapabilityMetadata
    initialized: bool = False
    stopped: bool = False

    def initialize(self, context: CapabilityContext) -> None:
        self.initialized = context.require("marker") == "available"

    def validate(self, request: CapabilityRequest) -> ValidationResult:
        return ValidationResult(request.operation == "run", "unsupported operation")

    def health(self) -> HealthReport:
        return HealthReport(HealthStatus.HEALTHY, "ready")

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult(True, data=request.arguments)

    def rollback(self, rollback_token: str) -> CapabilityResult:
        return CapabilityResult(True, data=rollback_token)

    def shutdown(self) -> None:
        self.stopped = True


def test_registration_discovery_and_ranking_are_metadata_only():
    registry = CapabilityRegistry()
    loaded = 0

    def factory(context: CapabilityContext) -> ProbeCapability:
        nonlocal loaded
        loaded += 1
        return ProbeCapability(metadata)

    metadata = CapabilityMetadata(
        "probe", "Test provider", supported_intents=("task.test",), permissions=("test",), legacy_ids=("legacy_probe",), priority=20
    )
    registry.register(metadata, factory)
    registry.initialize(CapabilityContext({"marker": "available"}))

    assert registry.discover(intent="task.test") == [metadata]
    assert registry.rank(intent="task.test", required_permissions=("test",)) == [metadata]
    assert registry.resolve_name("legacy_probe") == "probe"
    assert loaded == 0

    with pytest.raises(ValueError, match="already registered"):
        registry.register(metadata, factory)


def test_lazy_loading_dependency_injection_health_and_shutdown():
    registry = CapabilityRegistry()
    created: list[ProbeCapability] = []
    metadata = CapabilityMetadata("probe", "Test provider", dependencies=("marker",))

    def factory(context: CapabilityContext) -> ProbeCapability:
        capability = ProbeCapability(metadata)
        created.append(capability)
        return capability

    registry.register(metadata, factory)
    registry.initialize(CapabilityContext({"marker": "available"}))

    assert created == []
    assert registry.health("probe").status is HealthStatus.HEALTHY
    assert len(created) == 1
    assert created[0].initialized is True
    assert registry.execute("probe", CapabilityRequest("run", {"value": 7})).data == {"value": 7}
    assert registry.rollback("probe", "token").ok is True

    registry.shutdown()

    assert created[0].stopped is True


def test_missing_dependencies_are_reported_before_factory_execution():
    registry = CapabilityRegistry()
    metadata = CapabilityMetadata("dependent", "Needs a missing service", dependencies=("missing",))
    registry.register(metadata, lambda context: ProbeCapability(metadata))
    registry.initialize(CapabilityContext())

    with pytest.raises(LookupError, match="missing dependencies"):
        registry.get("dependent")


def test_builtin_registry_discovers_without_importing_and_adapts_existing_module():
    registry = build_builtin_registry()

    assert "code_execution" in registry.registered_names()
    assert registry.discover(intent="info.weather")[0].name == "weather"
    assert registry.health("code_execution", refresh=False).status is HealthStatus.HEALTHY

    result = registry.execute(
        "code_execution",
        CapabilityRequest("run_python", {"args": ["print('registry adapter')"]}),
    )

    assert result.ok is True
    assert "registry adapter" in result.data.stdout
