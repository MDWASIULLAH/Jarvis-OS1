"""Registry-backed Tool Executor for validated ExecutionPlans.

This module intentionally does not plan, route, mutate decisions, or import
specific capabilities. It only invokes capabilities supplied by the registry.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import replace

from ..capabilities.contracts import CapabilityResult
from ..capabilities.registry import CapabilityRegistry
from ..events.bus import EventBus
from ..events.model import (
    CapabilityCompleted,
    CapabilityCompletedPayload,
    CapabilityFailed,
    CapabilityFailedPayload,
    CapabilityStarted,
    CapabilityStartedPayload,
    ExecutionCancelled,
    ExecutionCancelledPayload,
    ExecutionCompleted,
    ExecutionCompletedPayload,
    ExecutionRolledBack,
    ExecutionRolledBackPayload,
    ExecutionStarted,
    ExecutionStartedPayload,
    ExecutionTimedOut,
    ExecutionTimedOutPayload,
)
from ..planning.models import ExecutionMode, ExecutionPlan, PlanStep, RollbackMode
from .context import (
    CapabilityCompatibilityAdapter,
    CancellationToken,
    ContextAttribute,
    ExecutionContext,
    TimeoutManager,
)
from .middleware import ExecutionMiddleware, MiddlewarePipeline
from .models import (
    ExecutionMetrics,
    ExecutionResult,
    ExecutionState,
    FailureReport,
    RetryInfo,
    RollbackReport,
    StepResult,
    TimingInfo,
)


class ToolExecutor:
    """Executes one plan at a time with only local per-request state."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        event_bus: EventBus | None = None,
        middleware: tuple[ExecutionMiddleware, ...] = (),
    ):
        self._registry = registry
        self._event_bus = event_bus
        self._capability_adapter = CapabilityCompatibilityAdapter()
        self._middleware_lock = threading.RLock()
        self._middleware = MiddlewarePipeline(middleware)

    def register_middleware(self, middleware: ExecutionMiddleware) -> None:
        """Add middleware without coupling it to capabilities or plan logic."""
        with self._middleware_lock:
            self._middleware = self._middleware.with_middleware(middleware)

    def _create_context(
        self,
        plan: ExecutionPlan,
        *,
        execution_context: ExecutionContext | None,
        cancellation: CancellationToken | None,
        correlation_id: str | None,
        deadline: float | None,
        conversation_id: str | None,
        session_id: str | None,
        user_id: str | None,
        metadata: tuple[ContextAttribute, ...],
    ) -> ExecutionContext:
        if execution_context is None:
            return ExecutionContext.create(
                plan,
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                session_id=session_id,
                user_id=user_id,
                cancellation_token=cancellation,
                timeout_manager=TimeoutManager(deadline),
                metadata=metadata,
            )
        if execution_context.execution_plan.plan_id != plan.plan_id:
            raise ValueError("ExecutionContext belongs to a different execution plan.")
        replacements: dict[str, object] = {}
        if cancellation is not None and cancellation is not execution_context.cancellation_token:
            replacements["cancellation_token"] = cancellation
        if correlation_id is not None and correlation_id != execution_context.correlation_id:
            replacements["correlation_id"] = correlation_id
        if deadline is not None:
            replacements["timeout_manager"] = TimeoutManager(deadline)
        return replace(execution_context, **replacements) if replacements else execution_context

    def _middleware_snapshot(self) -> MiddlewarePipeline:
        with self._middleware_lock:
            return self._middleware

    async def _invoke_capability(self, context: ExecutionContext) -> CapabilityResult:
        """Resolve the implementation through the registry, then use its adapter."""
        return await asyncio.to_thread(self._invoke_registered_capability, context)

    def _invoke_registered_capability(self, context: ExecutionContext) -> CapabilityResult:
        step = context.current_step
        if step is None or step.capability_id is None:
            raise ValueError("ExecutionContext does not identify a capability step.")
        capability = self._registry.get(step.capability_id)
        return self._capability_adapter.execute(capability, context)

    def execute(
        self,
        plan: ExecutionPlan,
        *,
        cancellation: CancellationToken | None = None,
        plan_timeout_seconds: float | None = None,
        correlation_id: str | None = None,
        execution_context: ExecutionContext | None = None,
        conversation_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: tuple[ContextAttribute, ...] = (),
    ) -> ExecutionResult:
        """Synchronous compatibility entry point for callers outside an event loop."""
        return asyncio.run(
            self.execute_async(
                plan,
                cancellation=cancellation,
                plan_timeout_seconds=plan_timeout_seconds,
                correlation_id=correlation_id,
                execution_context=execution_context,
                conversation_id=conversation_id,
                session_id=session_id,
                user_id=user_id,
                metadata=metadata,
            )
        )

    async def execute_async(
        self,
        plan: ExecutionPlan,
        *,
        cancellation: CancellationToken | None = None,
        plan_timeout_seconds: float | None = None,
        correlation_id: str | None = None,
        execution_context: ExecutionContext | None = None,
        conversation_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: tuple[ContextAttribute, ...] = (),
    ) -> ExecutionResult:
        """Execute a validated DAG while preserving dependency and failure state."""
        started = time.monotonic()
        deadline = started + plan_timeout_seconds if plan_timeout_seconds is not None else None
        context = self._create_context(
            plan,
            execution_context=execution_context,
            cancellation=cancellation,
            correlation_id=correlation_id,
            deadline=deadline,
            conversation_id=conversation_id,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata,
        )
        plan_errors = plan.validate()
        if plan_errors:
            return self._invalid_plan_result(plan, context.execution_id, started, plan_errors)

        self._publish(ExecutionStarted(source="tool_executor", payload=ExecutionStartedPayload(context.execution_id, plan.plan_id), correlation_id=context.correlation_id))
        results: dict[str, StepResult] = {}
        cancellation = context.cancellation_token
        deadline = context.timeout_manager.deadline_monotonic
        timed_out = False

        for layer in plan.topological_layers():
            if cancellation.cancelled:
                self._cancel_pending(plan, results, cancellation.reason)
                break
            if deadline is not None and time.monotonic() >= deadline:
                timed_out = True
                self._timeout_pending(plan, results, "Whole-plan timeout exceeded.")
                self._publish(ExecutionTimedOut(source="tool_executor", payload=ExecutionTimedOutPayload(context.execution_id, plan.plan_id), correlation_id=context.correlation_id))
                break

            steps = [self._find_step(plan, step_id) for step_id in layer]
            runnable, skipped = self._eligible_steps(steps, results)
            results.update(skipped)
            sequential = [step for step in runnable if not step.can_run_parallel and step.execution_mode is not ExecutionMode.PARALLEL]
            parallel = [step for step in runnable if step not in sequential]

            for step in sequential:
                if cancellation.cancelled:
                    self._cancel_pending(plan, results, cancellation.reason)
                    break
                result = await self._execute_step(step, context)
                results[step.step_id] = result
                if self._was_plan_timeout(result):
                    timed_out = True
                    self._timeout_pending(plan, results, "Whole-plan timeout exceeded.")
                    self._publish(ExecutionTimedOut(source="tool_executor", payload=ExecutionTimedOutPayload(context.execution_id, plan.plan_id), correlation_id=context.correlation_id))
                    break
            if cancellation.cancelled:
                break
            if timed_out:
                break
            if parallel:
                completed = await asyncio.gather(
                    *(
                        self._execute_step(step, context)
                        for step in parallel
                    )
                )
                results.update({result.step_id: result for result in completed})
                if any(self._was_plan_timeout(result) for result in completed):
                    timed_out = True

            # Re-check at the layer boundary.  A step may have consumed the
            # remaining whole-plan budget without leaving enough time for the
            # next dependency layer to be considered.
            if timed_out or (deadline is not None and time.monotonic() >= deadline):
                timed_out = True
                self._timeout_pending(plan, results, "Whole-plan timeout exceeded.")
                self._publish(ExecutionTimedOut(source="tool_executor", payload=ExecutionTimedOutPayload(context.execution_id, plan.plan_id), correlation_id=context.correlation_id))
                break

        if cancellation.cancelled:
            self._cancel_pending(plan, results, cancellation.reason)
            self._publish(ExecutionCancelled(source="tool_executor", payload=ExecutionCancelledPayload(context.execution_id, plan.plan_id, cancellation.reason), correlation_id=context.correlation_id))
        if timed_out:
            self._timeout_pending(plan, results, "Whole-plan timeout exceeded.")

        rollbacks = await self._rollback_if_required(plan, results, context)
        if rollbacks:
            self._publish(ExecutionRolledBack(source="tool_executor", payload=ExecutionRolledBackPayload(context.execution_id, plan.plan_id, len(rollbacks)), correlation_id=context.correlation_id))

        result = self._result(plan, context, started, results, rollbacks, cancellation.cancelled, timed_out)
        self._publish(ExecutionCompleted(source="tool_executor", payload=ExecutionCompletedPayload(context.execution_id, plan.plan_id, result.state.value), correlation_id=context.correlation_id))
        return result

    async def _execute_step(
        self,
        step: PlanStep,
        context: ExecutionContext,
    ) -> StepResult:
        context = context.for_step(step)
        started = time.monotonic()
        if context.cancellation_token.cancelled:
            return self._cancelled_step(step, context.cancellation_token.reason, started)
        if step.capability_id is None:
            return self._failed_step(step, "MissingCapability", "Plan step does not identify a capability.", started)

        self._publish(CapabilityStarted(source="tool_executor", payload=CapabilityStartedPayload(step.capability_id, self._operation(step), step.step_id), correlation_id=context.correlation_id))
        attempts = 0
        max_attempts = max(1, step.retry_policy.max_attempts)
        last_failure: FailureReport | None = None
        while attempts < max_attempts:
            attempts += 1
            if context.cancellation_token.cancelled:
                return self._cancelled_step(step, context.cancellation_token.reason, started, attempts, max_attempts)
            timeout, is_plan_timeout = self._effective_timeout(step.timeout_seconds, context.timeout_manager.deadline_monotonic)
            if timeout is not None and timeout <= 0:
                return self._timed_out_step(step, "Whole-plan timeout exceeded.", "PlanTimeout", started, attempts, max_attempts, context)
            try:
                outcome = await asyncio.wait_for(
                    self._middleware_snapshot().execute(context, self._invoke_capability),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                message = "Whole-plan timeout exceeded." if is_plan_timeout else "Step timeout exceeded."
                error_type = "PlanTimeout" if is_plan_timeout else "Timeout"
                return self._timed_out_step(step, message, error_type, started, attempts, max_attempts, context)
            except Exception as exc:
                outcome = CapabilityResult(False, message=str(exc))

            if outcome.ok:
                completed = time.monotonic()
                result = StepResult(
                    step.step_id,
                    step.capability_id,
                    ExecutionState.COMPLETED,
                    output=outcome,
                    timing=TimingInfo(started, completed, completed - started),
                    retry=RetryInfo(attempts, max_attempts, False),
                )
                self._publish(CapabilityCompleted(source="tool_executor", payload=CapabilityCompletedPayload(step.capability_id, self._operation(step), outcome.rollback_token, step.step_id), correlation_id=context.correlation_id))
                return result
            last_failure = FailureReport(step.step_id, step.capability_id, "CapabilityError", outcome.message or "Capability returned an unsuccessful result.")
            if attempts < max_attempts and step.retry_policy.backoff_seconds > 0:
                await asyncio.sleep(step.retry_policy.backoff_seconds)

        completed = time.monotonic()
        failure = last_failure or FailureReport(step.step_id, step.capability_id, "CapabilityError", "Capability failed.")
        result = StepResult(
            step.step_id,
            step.capability_id,
            ExecutionState.FAILED,
            timing=TimingInfo(started, completed, completed - started),
            retry=RetryInfo(attempts, max_attempts, True),
            failure=failure,
        )
        self._publish(CapabilityFailed(source="tool_executor", payload=CapabilityFailedPayload(step.capability_id, self._operation(step), failure.error_type, failure.message, step.step_id), correlation_id=context.correlation_id))
        return result

    @staticmethod
    def _operation(step: PlanStep) -> str:
        return next((field.value for field in step.metadata if field.name == "operation"), "")

    @staticmethod
    def _effective_timeout(step_timeout: float | None, deadline: float | None) -> tuple[float | None, bool]:
        remaining = None if deadline is None else deadline - time.monotonic()
        if step_timeout is None:
            return remaining, deadline is not None
        if remaining is None or step_timeout <= remaining:
            return step_timeout, False
        return remaining, True

    @staticmethod
    def _find_step(plan: ExecutionPlan, step_id: str) -> PlanStep:
        return next(step for step in plan.steps if step.step_id == step_id)

    @staticmethod
    def _eligible_steps(steps: list[PlanStep], results: dict[str, StepResult]) -> tuple[list[PlanStep], dict[str, StepResult]]:
        runnable: list[PlanStep] = []
        skipped: dict[str, StepResult] = {}
        for step in steps:
            unmet = [dependency for dependency in step.dependencies if results.get(dependency.prerequisite_step_id, None) is None or results[dependency.prerequisite_step_id].state is not ExecutionState.COMPLETED]
            if unmet:
                reason = "Prerequisite step did not complete successfully."
                skipped[step.step_id] = StepResult(
                    step.step_id,
                    step.capability_id,
                    ExecutionState.SKIPPED,
                    failure=FailureReport(step.step_id, step.capability_id, "DependencyFailure", reason),
                )
            else:
                runnable.append(step)
        return runnable, skipped

    @staticmethod
    def _cancel_pending(plan: ExecutionPlan, results: dict[str, StepResult], reason: str) -> None:
        for step in plan.steps:
            if step.step_id not in results:
                results[step.step_id] = StepResult(
                    step.step_id, step.capability_id, ExecutionState.CANCELLED,
                    failure=FailureReport(step.step_id, step.capability_id, "Cancelled", reason),
                )

    @staticmethod
    def _timeout_pending(plan: ExecutionPlan, results: dict[str, StepResult], reason: str) -> None:
        for step in plan.steps:
            if step.step_id not in results:
                results[step.step_id] = StepResult(
                    step.step_id, step.capability_id, ExecutionState.TIMED_OUT,
                    failure=FailureReport(step.step_id, step.capability_id, "Timeout", reason),
                )

    def _timed_out_step(self, step: PlanStep, message: str, error_type: str, started: float, attempts: int, max_attempts: int, context: ExecutionContext) -> StepResult:
        completed = time.monotonic()
        failure = FailureReport(step.step_id, step.capability_id, error_type, message)
        self._publish(ExecutionTimedOut(source="tool_executor", payload=ExecutionTimedOutPayload(context.execution_id, context.execution_plan.plan_id, step.step_id), correlation_id=context.correlation_id))
        self._publish(CapabilityFailed(source="tool_executor", payload=CapabilityFailedPayload(step.capability_id or "", self._operation(step), failure.error_type, message, step.step_id), correlation_id=context.correlation_id))
        return StepResult(step.step_id, step.capability_id, ExecutionState.TIMED_OUT, timing=TimingInfo(started, completed, completed - started), retry=RetryInfo(attempts, max_attempts, True), failure=failure)

    @staticmethod
    def _was_plan_timeout(result: StepResult) -> bool:
        return result.failure is not None and result.failure.error_type == "PlanTimeout"

    @staticmethod
    def _failed_step(step: PlanStep, error_type: str, message: str, started: float) -> StepResult:
        completed = time.monotonic()
        return StepResult(step.step_id, step.capability_id, ExecutionState.FAILED, timing=TimingInfo(started, completed, completed - started), failure=FailureReport(step.step_id, step.capability_id, error_type, message))

    @staticmethod
    def _cancelled_step(step: PlanStep, reason: str, started: float, attempts: int = 0, max_attempts: int = 1) -> StepResult:
        completed = time.monotonic()
        return StepResult(step.step_id, step.capability_id, ExecutionState.CANCELLED, timing=TimingInfo(started, completed, completed - started), retry=RetryInfo(attempts, max_attempts), failure=FailureReport(step.step_id, step.capability_id, "Cancelled", reason))

    async def _rollback_if_required(self, plan: ExecutionPlan, results: dict[str, StepResult], context: ExecutionContext) -> tuple[RollbackReport, ...]:
        trigger = any(result.state in {ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.TIMED_OUT} for result in results.values())
        if not trigger:
            return ()
        reports: list[RollbackReport] = []
        step_by_id = {step.step_id: step for step in plan.steps}
        for result in list(results.values()):
            step = step_by_id[result.step_id]
            if result.state is not ExecutionState.COMPLETED or step.rollback_policy.mode is not RollbackMode.AUTOMATIC:
                continue
            token = result.output.rollback_token if result.output else None
            if not token or step.capability_id is None:
                continue
            try:
                outcome = await asyncio.to_thread(self._registry.rollback, step.capability_id, token)
                report = RollbackReport(step.step_id, step.capability_id, True, outcome.ok, outcome.message)
            except Exception as exc:
                report = RollbackReport(step.step_id, step.capability_id, True, False, str(exc))
            reports.append(report)
            if report.succeeded:
                results[step.step_id] = replace(result, state=ExecutionState.ROLLED_BACK, rollback=report)
            else:
                results[step.step_id] = replace(result, rollback=report)
        return tuple(reports)

    @staticmethod
    def _result(
        plan: ExecutionPlan,
        context: ExecutionContext,
        started: float,
        results: dict[str, StepResult],
        rollbacks: tuple[RollbackReport, ...],
        cancelled: bool,
        timed_out: bool,
    ) -> ExecutionResult:
        ordered = tuple(results.get(step.step_id, StepResult(step.step_id, step.capability_id, ExecutionState.WAITING)) for step in plan.steps)
        failures = tuple(result.failure for result in ordered if result.failure is not None)
        duration = time.monotonic() - started
        metrics = ExecutionMetrics(
            total_steps=len(plan.steps),
            completed_steps=sum(result.state is ExecutionState.COMPLETED for result in ordered),
            failed_steps=sum(result.state is ExecutionState.FAILED for result in ordered),
            skipped_steps=sum(result.state is ExecutionState.SKIPPED for result in ordered),
            cancelled_steps=sum(result.state is ExecutionState.CANCELLED for result in ordered),
            timed_out_steps=sum(result.state is ExecutionState.TIMED_OUT for result in ordered),
            rolled_back_steps=sum(result.state is ExecutionState.ROLLED_BACK for result in ordered),
            duration_seconds=duration,
        )
        for step in ordered:
            context.metrics.increment(f"steps.{step.state.value}")
        state = (
            ExecutionState.TIMED_OUT if timed_out or metrics.timed_out_steps else
            ExecutionState.CANCELLED if cancelled or metrics.cancelled_steps else
            ExecutionState.ROLLED_BACK if metrics.rolled_back_steps else
            ExecutionState.FAILED if metrics.failed_steps else
            ExecutionState.COMPLETED
        )
        completed = time.monotonic()
        context.metrics.increment(f"executions.{state.value}")
        return ExecutionResult(plan.plan_id, context.execution_id, state, ordered, metrics, failures, rollbacks, TimingInfo(started, completed, completed - started))

    @staticmethod
    def _invalid_plan_result(plan: ExecutionPlan, execution_id: str, started: float, errors: tuple[str, ...]) -> ExecutionResult:
        completed = time.monotonic()
        failures = tuple(FailureReport(None, None, "InvalidPlan", error) for error in errors)
        return ExecutionResult(
            plan.plan_id,
            execution_id,
            ExecutionState.FAILED,
            failures=failures,
            metrics=ExecutionMetrics(len(plan.steps), 0, 0, 0, 0, 0, 0, completed - started),
            timing=TimingInfo(started, completed, completed - started),
        )

    def _publish(self, event: object) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)  # type: ignore[arg-type]
