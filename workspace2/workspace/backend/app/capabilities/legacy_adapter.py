"""Compatibility adapter for the existing capability modules.

Legacy modules remain importable and callable exactly as they are today. This
adapter gives them the common capability lifecycle without rewriting stable
provider implementations during the registry phase.
"""

from __future__ import annotations

import importlib
import time
from types import ModuleType
from typing import Any

from .contracts import (
    CapabilityContext,
    CapabilityMetadata,
    CapabilityRequest,
    CapabilityResult,
    HealthReport,
    HealthStatus,
    ValidationResult,
)


class LegacyModuleCapability:
    """Lazily adapts public functions from one existing module.

    A request uses ``operation`` plus optional ``args`` (a list) and ``kwargs``
    (a mapping). A ``service_name`` can instead target an already composed
    runtime service such as ``weather`` or ``email`` while preserving the same
    legacy method signatures.
    """

    def __init__(
        self,
        metadata: CapabilityMetadata,
        module_path: str,
        *,
        service_name: str | None = None,
        health_probe: str | None = None,
    ) -> None:
        self.metadata = metadata
        self._module_path = module_path
        self._service_name = service_name
        self._health_probe = health_probe
        self._context: CapabilityContext | None = None
        self._module: ModuleType | None = None

    def initialize(self, context: CapabilityContext) -> None:
        self._context = context
        self._module = importlib.import_module(self._module_path)

    def validate(self, request: CapabilityRequest) -> ValidationResult:
        if not request.operation:
            return ValidationResult(False, "An operation is required.")
        if request.operation.startswith("_"):
            return ValidationResult(False, "Private operations are not callable through the capability adapter.")
        try:
            operation = getattr(self._target(), request.operation)
        except AttributeError:
            return ValidationResult(False, f"Unsupported operation: {request.operation}")
        if not callable(operation):
            return ValidationResult(False, f"Operation is not callable: {request.operation}")
        args = request.arguments.get("args", [])
        kwargs = request.arguments.get("kwargs", {})
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            return ValidationResult(False, "Adapter arguments require a list 'args' and dictionary 'kwargs'.")
        return ValidationResult(True)

    def health(self) -> HealthReport:
        try:
            target = self._target()
            if self._health_probe:
                probe = getattr(target, self._health_probe)
                outcome = probe()
                if outcome is False:
                    return HealthReport(HealthStatus.DEGRADED, "Availability probe returned false.", time.time())
            return HealthReport(HealthStatus.HEALTHY, "Legacy provider loaded.", time.time())
        except Exception as exc:
            return HealthReport(HealthStatus.UNHEALTHY, str(exc), time.time())

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        validation = self.validate(request)
        if not validation.valid:
            return CapabilityResult(False, message=validation.reason)
        operation = getattr(self._target(), request.operation)
        try:
            result = operation(*request.arguments.get("args", []), **request.arguments.get("kwargs", {}))
            return CapabilityResult(True, data=result)
        except Exception as exc:
            return CapabilityResult(False, message=str(exc))

    def rollback(self, rollback_token: str) -> CapabilityResult:
        return CapabilityResult(False, message="This legacy capability does not support rollback yet.")

    def shutdown(self) -> None:
        self._context = None
        self._module = None

    def _target(self) -> Any:
        if self._context is None:
            raise RuntimeError(f"Capability '{self.metadata.name}' has not been initialized.")
        if self._service_name:
            return self._context.require(self._service_name)
        if self._module is None:
            raise RuntimeError(f"Capability module was not loaded: {self._module_path}")
        return self._module
