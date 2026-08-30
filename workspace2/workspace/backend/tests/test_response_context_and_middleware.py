from __future__ import annotations

import asyncio

from app.execution.context import ExecutionContext
from app.execution.models import ExecutionResult, ExecutionState, FailureReport
from app.planning.models import ExecutionPlan, PlanField, PlanStep
from app.responses.context import (
    Citation,
    OutputFormat,
    ResponseArtifact,
    ResponseAttachment,
    ResponseContext,
    Tone,
    UserPreferences,
)
from app.responses.middleware import ResponseError, ResponseMiddlewarePipeline, ResponseMiddlewareRegistry, ResponseOutput


class RecordingResponseMiddleware:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def before_response(self, context: ResponseContext) -> ResponseContext:
        self.events.append(f"before:{self.name}")
        return context

    def after_response(self, context: ResponseContext, response: ResponseOutput) -> ResponseOutput:
        self.events.append(f"after:{self.name}")
        return ResponseOutput(f"{response.content}-{self.name}", response.output_format, response.is_partial)

    def error_response(self, context: ResponseContext, error: ResponseError) -> ResponseOutput | None:
        self.events.append(f"error:{self.name}")
        return None


class RecoveryResponseMiddleware(RecordingResponseMiddleware):
    def error_response(self, context: ResponseContext, error: ResponseError) -> ResponseOutput | None:
        self.events.append(f"error:{self.name}")
        return ResponseOutput("recovered", context.output_format, is_partial=True)


def _execution_inputs() -> tuple[ExecutionResult, ExecutionContext]:
    plan = ExecutionPlan.new(
        "decision",
        "response-context",
        (PlanStep("capability", "capability", "capability", "capability", metadata=(PlanField("operation", "run"),)),),
    )
    context = ExecutionContext.create(plan, execution_id="execution-1", correlation_id="correlation-1", conversation_id="conversation-1")
    result = ExecutionResult(
        plan_id=plan.plan_id,
        execution_id="execution-1",
        state=ExecutionState.FAILED,
        failures=(FailureReport("capability", "capability", "CapabilityError", "failed"),),
    )
    return result, context


def test_response_context_construction_derives_stable_execution_and_failure_data():
    result, execution_context = _execution_inputs()
    context = ResponseContext.create(
        result,
        execution_context,
        response_id="response-1",
        user_preferences=UserPreferences(preferred_format=OutputFormat.TEXT, tone=Tone.CONCISE),
        output_format=OutputFormat.MARKDOWN,
        streaming_enabled=True,
        language="hi",
        tone=Tone.PROFESSIONAL,
        citations=(Citation("citation-1", "Docs", "JARVIS docs"),),
        attachments=(ResponseAttachment("attachment-1", "result.txt", "text/plain"),),
        artifacts=(ResponseArtifact("artifact-1", "report", "file"),),
    )

    assert context.response_id == "response-1"
    assert context.execution_result is result
    assert context.conversation_context is not None and context.conversation_context.conversation_id == "conversation-1"
    assert context.partial_failures[0].message == "failed"
    assert context.telemetry is not None and context.telemetry.correlation_id == "correlation-1"
    assert context.streaming_enabled is True and context.output_format is OutputFormat.MARKDOWN


def test_response_middleware_registration_order_and_chaining_are_deterministic():
    result, execution_context = _execution_inputs()
    context = ResponseContext.create(result, execution_context)
    events: list[str] = []
    registry = ResponseMiddlewareRegistry((RecordingResponseMiddleware("first", events),))
    registry.register(RecordingResponseMiddleware("second", events))

    async def build(value: ResponseContext) -> ResponseOutput:
        events.append("build")
        return ResponseOutput("response", value.output_format)

    output = asyncio.run(registry.snapshot().execute(context, build))

    assert events == ["before:first", "before:second", "build", "after:second", "after:first"]
    assert output.content == "response-second-first"


def test_response_middleware_error_hook_can_provide_a_typed_partial_output():
    result, execution_context = _execution_inputs()
    context = ResponseContext.create(result, execution_context)
    events: list[str] = []
    pipeline = ResponseMiddlewarePipeline((RecoveryResponseMiddleware("recovery", events),))

    async def build(value: ResponseContext) -> ResponseOutput:
        raise RuntimeError("builder unavailable")

    output = asyncio.run(pipeline.execute(context, build))

    assert events == ["before:recovery", "error:recovery"]
    assert output == ResponseOutput("recovered", OutputFormat.MARKDOWN, is_partial=True)


def test_response_context_accepts_current_execution_contracts_without_changing_them():
    result, execution_context = _execution_inputs()

    context = ResponseContext.create(result, execution_context)

    assert context.execution_context.execution_id == result.execution_id
    assert context.user_preferences == UserPreferences()
    assert context.citations == () and context.attachments == () and context.artifacts == ()
