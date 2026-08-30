from __future__ import annotations

import asyncio
import json

import pytest

from app.events.bus import EventBus
from app.events.model import EventType
from app.execution.context import ExecutionContext
from app.execution.models import ExecutionMetrics, ExecutionResult, ExecutionState, FailureReport, StepResult
from app.planning.models import ExecutionPlan, PlanField, PlanStep
from app.responses.builder import ResponseBuilder
from app.responses.context import Attachment, Citation, OutputFormat, ResponseArtifact, ResponseAttachment, ResponseContext
from app.responses.middleware import ResponseError, ResponseMiddlewarePipeline, ResponseMiddlewareRegistry, ResponseOutput
from app.responses.models import Response
from app.responses.rendering import ResponseFormatter
from app.responses.strategies import ArtifactResponseStrategy, ArtifactStrategy, MarkdownResponseStrategy, MarkdownStrategy, SimpleResponseStrategy, StreamingResponseStrategy, StreamingStrategy, StructuredResponseStrategy, StructuredStrategy


class SuffixMiddleware:
    def before_response(self, context: ResponseContext) -> ResponseContext:
        return context

    def after_response(self, context: ResponseContext, response: Response) -> Response:
        return Response(
            content=response.content + "\nMiddleware applied.",
            output_format=response.output_format,
            response_id=response.response_id,
            status=response.status,
            is_partial=response.is_partial,
            citations=response.citations,
            images=response.images,
            tables=response.tables,
            artifacts=response.artifacts,
            attachments=response.attachments,
            partial_failures=response.partial_failures,
            metadata=response.metadata,
        )

    def error_response(self, context: ResponseContext, error: ResponseError) -> Response | None:
        return None


class FailingFormatter(ResponseFormatter):
    def format(self, context: ResponseContext, rendered):
        raise RuntimeError("formatting failed")


class PreferredErrorMiddleware:
    def before_response(self, context: ResponseContext) -> ResponseContext:
        return context

    def after_response(self, context: ResponseContext, response: Response) -> Response:
        return response

    def error_response(self, context: ResponseContext, error: ResponseError) -> Response | None:
        raise AssertionError("Legacy hook should not be selected when on_error exists.")

    def on_error(self, context: ResponseContext, error: ResponseError) -> Response | None:
        return Response("recovered", context.output_format, response_id=context.response_id, is_partial=True)


def _context(
    *,
    output_format: OutputFormat = OutputFormat.TEXT,
    streaming: bool = False,
    partial: bool = False,
    artifacts: tuple[ResponseArtifact, ...] = (),
    attachments: tuple[ResponseAttachment, ...] = (),
) -> ResponseContext:
    plan = ExecutionPlan.new(
        "decision",
        "response",
        (PlanStep("search", "search", "search", "search", metadata=(PlanField("operation", "run"),)),),
    )
    execution_context = ExecutionContext.create(plan, execution_id="execution-1", correlation_id="correlation-1")
    failure = FailureReport("search", "search", "CapabilityError", "source unavailable")
    steps = (StepResult("search", "search", ExecutionState.FAILED if partial else ExecutionState.COMPLETED, failure=failure if partial else None),)
    result = ExecutionResult(
        plan_id=plan.plan_id,
        execution_id="execution-1",
        state=ExecutionState.FAILED if partial else ExecutionState.COMPLETED,
        steps=steps,
        metrics=ExecutionMetrics(1, 0 if partial else 1, 1 if partial else 0, 0, 0, 0, 0, 0.0),
        failures=(failure,) if partial else (),
    )
    return ResponseContext.create(
        result,
        execution_context,
        response_id="response-1",
        output_format=output_format,
        streaming_enabled=streaming,
        citations=(Citation("citation-1", "Reference", "docs", "https://example.test/docs"),),
        artifacts=artifacts,
        attachments=attachments,
    )


def test_builder_formats_plain_text_markdown_and_structured_json():
    text = ResponseBuilder().build(_context())
    markdown = ResponseBuilder().build(_context(output_format=OutputFormat.MARKDOWN))
    structured = ResponseBuilder().build(_context(output_format=OutputFormat.JSON))

    assert "Execution completed." in text.content
    assert "## Execution result" in markdown.content and "| Step | Status | Details |" in markdown.content
    assert json.loads(structured.content)["execution_state"] == "completed"


def test_builder_preserves_partial_failures_citations_images_tables_and_artifacts():
    artifact = ResponseArtifact("artifact-1", "report.pdf", "file", "results/report.pdf")
    image = ResponseAttachment("image-1", "chart.png", "image/png", "results/chart.png")

    response = ResponseBuilder().build(_context(partial=True, artifacts=(artifact,), attachments=(image,)))

    assert response.is_partial is True
    assert response.partial_failures[0].message == "source unavailable"
    assert response.citations[0].label == "Reference"
    assert response.images[0].location == "results/chart.png"
    assert response.tables[0].headers == ("Step", "Status", "Details")
    assert response.artifacts == (artifact,) and "Artifacts: report.pdf, chart.png" in response.content


def test_builder_creates_ordered_streaming_response():
    streamed = ResponseBuilder().build_stream(_context(streaming=True), chunk_size=10)

    assert streamed.response.response_id == "response-1"
    assert "".join(chunk.content for chunk in streamed) == streamed.response.content
    assert streamed.chunks[-1].is_final is True


def test_strategy_selection_covers_simple_markdown_structured_streaming_and_artifact_responses():
    builder = ResponseBuilder()

    assert isinstance(builder.strategy_for(_context()), SimpleResponseStrategy)
    assert isinstance(builder.strategy_for(_context(output_format=OutputFormat.MARKDOWN)), MarkdownStrategy)
    assert isinstance(builder.strategy_for(_context(output_format=OutputFormat.JSON)), StructuredStrategy)
    assert isinstance(builder.strategy_for(_context(streaming=True)), StreamingStrategy)
    assert isinstance(builder.strategy_for(_context(artifacts=(ResponseArtifact("a", "report", "file"),))), ArtifactStrategy)
    assert MarkdownResponseStrategy is MarkdownStrategy
    assert StructuredResponseStrategy is StructuredStrategy
    assert StreamingResponseStrategy is StreamingStrategy
    assert ArtifactResponseStrategy is ArtifactStrategy


def test_builder_uses_registered_response_middleware_and_publishes_events():
    events: list[EventType] = []
    bus = EventBus()
    bus.subscribe(None, lambda event: events.append(event.event_type))
    middleware = ResponseMiddlewareRegistry((SuffixMiddleware(),))

    response = ResponseBuilder(event_bus=bus, middleware_registry=middleware).build(_context())

    assert response.content.endswith("Middleware applied.")
    assert events == [EventType.RESPONSE_STARTED, EventType.RESPONSE_COMPLETED]


def test_builder_publishes_failed_event_and_preserves_response_output_compatibility():
    events: list[EventType] = []
    bus = EventBus()
    bus.subscribe(None, lambda event: events.append(event.event_type))

    with pytest.raises(RuntimeError, match="formatting failed"):
        ResponseBuilder(formatter=FailingFormatter(), event_bus=bus).build(_context())

    legacy_output = ResponseOutput("legacy", OutputFormat.TEXT, is_partial=True)
    assert legacy_output.content == "legacy" and legacy_output.is_partial is True
    assert events == [EventType.RESPONSE_STARTED, EventType.RESPONSE_FAILED]


def test_response_metrics_attachment_alias_and_preferred_error_hook_are_supported():
    response = ResponseBuilder().build(_context())
    attachment = Attachment("attachment-1", "output.txt", "text/plain")
    pipeline = ResponseMiddlewarePipeline((PreferredErrorMiddleware(),))

    async def fail(context: ResponseContext) -> Response:
        raise RuntimeError("unavailable")

    recovered = asyncio.run(pipeline.execute(_context(), fail))

    assert response.metrics.strategy_name == "simple"
    assert response.metrics.content_length == len(response.content)
    assert attachment == ResponseAttachment("attachment-1", "output.txt", "text/plain")
    assert recovered.content == "recovered" and recovered.is_partial is True
