"""Renderer and formatters used by response strategies."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .context import OutputFormat, ResponseContext
from .models import Response, ResponseImage, ResponseStatus, ResponseTable


@dataclass(frozen=True)
class RenderedResponse:
    summary: str
    table: ResponseTable
    images: tuple[ResponseImage, ...]


class ResponseRenderer:
    """Converts typed execution facts into a presentation-neutral document."""

    def render(self, context: ResponseContext) -> RenderedResponse:
        result = context.execution_result
        rows = tuple(
            (
                step.step_id,
                step.state.value,
                step.failure.message if step.failure is not None else (step.output.message if step.output is not None else ""),
            )
            for step in result.steps
        )
        summary = f"Execution {result.state.value}."
        if context.partial_failures:
            summary = f"{summary} {len(context.partial_failures)} step(s) did not complete."
        images = tuple(
            ResponseImage(item.attachment_id, item.name, item.location)
            for item in context.attachments
            if item.media_type.startswith("image/")
        )
        return RenderedResponse(summary, ResponseTable(("Step", "Status", "Details"), rows), images)


class ResponseFormatter:
    """Formats a rendered response without performing execution or routing."""

    def format(self, context: ResponseContext, rendered: RenderedResponse) -> Response:
        if context.output_format is OutputFormat.JSON:
            content = self._json_content(context, rendered)
        elif context.output_format is OutputFormat.MARKDOWN:
            content = self._markdown_content(context, rendered)
        else:
            content = self._text_content(context, rendered)
        partial = bool(context.partial_failures)
        return Response(
            content=content,
            output_format=context.output_format,
            response_id=context.response_id,
            status=ResponseStatus.PARTIAL if partial else ResponseStatus.COMPLETED,
            is_partial=partial,
            citations=context.citations,
            images=rendered.images,
            tables=(rendered.table,),
            artifacts=context.artifacts,
            attachments=context.attachments,
            partial_failures=context.partial_failures,
            metadata=context.metadata,
        )

    @staticmethod
    def _text_content(context: ResponseContext, rendered: RenderedResponse) -> str:
        lines = [rendered.summary]
        lines.extend(f"{row[0]}: {row[1]}{f' — {row[2]}' if row[2] else ''}" for row in rendered.table.rows)
        lines.extend(f"Citation: {citation.label} ({citation.source})" for citation in context.citations)
        return "\n".join(lines)

    @staticmethod
    def _markdown_content(context: ResponseContext, rendered: RenderedResponse) -> str:
        lines = [f"## Execution result\n\n{rendered.summary}"]
        lines.extend(("", "| Step | Status | Details |", "| --- | --- | --- |"))
        lines.extend(f"| {row[0]} | {row[1]} | {row[2]} |" for row in rendered.table.rows)
        if context.citations:
            lines.extend(("", "### Citations"))
            lines.extend(f"- [{citation.label}]({citation.url or citation.source})" for citation in context.citations)
        return "\n".join(lines)

    @staticmethod
    def _json_content(context: ResponseContext, rendered: RenderedResponse) -> str:
        payload = {
            "response_id": context.response_id,
            "execution_state": context.execution_result.state.value,
            "summary": rendered.summary,
            "steps": tuple(
                {"step_id": row[0], "status": row[1], "details": row[2]}
                for row in rendered.table.rows
            ),
            "partial_failures": tuple(
                {"step_id": item.step_id, "capability_id": item.capability_id, "error_type": item.error_type, "message": item.message}
                for item in context.partial_failures
            ),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
