"""Response strategy selection without execution-side responsibilities."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol, runtime_checkable

from .context import OutputFormat, ResponseContext
from .models import Response
from .rendering import ResponseFormatter, ResponseRenderer


@runtime_checkable
class ResponseStrategy(Protocol):
    """Selectable response-construction policy."""

    name: str

    def supports(self, context: ResponseContext) -> bool:
        """Return whether this policy applies to the context."""

    def build(self, context: ResponseContext, renderer: ResponseRenderer, formatter: ResponseFormatter) -> Response:
        """Create a response without capability, planning, or routing work."""


class SimpleResponseStrategy:
    name = "simple"

    def supports(self, context: ResponseContext) -> bool:
        return True

    def build(self, context: ResponseContext, renderer: ResponseRenderer, formatter: ResponseFormatter) -> Response:
        return formatter.format(context, renderer.render(context))


class MarkdownResponseStrategy(SimpleResponseStrategy):
    name = "markdown"

    def supports(self, context: ResponseContext) -> bool:
        return context.output_format is OutputFormat.MARKDOWN


class StructuredResponseStrategy(SimpleResponseStrategy):
    name = "structured"

    def supports(self, context: ResponseContext) -> bool:
        return context.output_format is OutputFormat.JSON


class StreamingResponseStrategy(SimpleResponseStrategy):
    name = "streaming"

    def supports(self, context: ResponseContext) -> bool:
        return context.streaming_enabled

    def build(self, context: ResponseContext, renderer: ResponseRenderer, formatter: ResponseFormatter) -> Response:
        return replace(super().build(context, renderer, formatter), metadata=(*context.metadata,))


class ArtifactResponseStrategy(SimpleResponseStrategy):
    name = "artifact"

    def supports(self, context: ResponseContext) -> bool:
        return bool(context.artifacts or context.attachments)

    def build(self, context: ResponseContext, renderer: ResponseRenderer, formatter: ResponseFormatter) -> Response:
        response = super().build(context, renderer, formatter)
        references = [item.name for item in context.artifacts] + [item.name for item in context.attachments]
        if not references:
            return response
        suffix = "\n\nArtifacts: " + ", ".join(references)
        return replace(response, content=response.content + suffix)


# Phase-7 canonical names are explicit; the shorter early names remain valid.
MarkdownStrategy = MarkdownResponseStrategy
StructuredStrategy = StructuredResponseStrategy
StreamingStrategy = StreamingResponseStrategy
ArtifactStrategy = ArtifactResponseStrategy
