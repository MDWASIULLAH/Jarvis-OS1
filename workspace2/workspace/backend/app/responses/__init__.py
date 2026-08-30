"""Typed contracts and middleware primitives for future response construction."""

from .context import (
    Attachment,
    Citation,
    ConversationContext,
    OutputFormat,
    PartialFailure,
    ResponseArtifact,
    ResponseAttachment,
    ResponseAttribute,
    ResponseContext,
    ResponseTelemetry,
    Tone,
    UserPreferences,
)
from .middleware import (
    ResponseError,
    ResponseMiddleware,
    ResponseMiddlewarePipeline,
    ResponseMiddlewareRegistry,
    ResponseOutput,
)
from .builder import ResponseBuilder
from .models import Response, ResponseChunk, ResponseImage, ResponseMetrics, ResponseStatus, ResponseTable, StreamingResponse
from .rendering import ResponseFormatter, ResponseRenderer
from .strategies import (
    ArtifactResponseStrategy,
    ArtifactStrategy,
    MarkdownResponseStrategy,
    MarkdownStrategy,
    ResponseStrategy,
    SimpleResponseStrategy,
    StreamingResponseStrategy,
    StreamingStrategy,
    StructuredResponseStrategy,
    StructuredStrategy,
)

__all__ = [
    "Attachment", "Citation", "ConversationContext", "OutputFormat", "PartialFailure", "ResponseArtifact",
    "ResponseAttachment", "ResponseAttribute", "ResponseContext", "ResponseError", "ResponseMiddleware",
    "ResponseMiddlewarePipeline", "ResponseMiddlewareRegistry", "ResponseOutput", "ResponseTelemetry", "Tone",
    "UserPreferences", "ResponseBuilder", "Response", "ResponseChunk", "ResponseImage", "ResponseMetrics", "ResponseStatus",
    "ResponseTable", "StreamingResponse", "ResponseFormatter", "ResponseRenderer", "ArtifactStrategy",
    "ArtifactResponseStrategy", "MarkdownResponseStrategy", "MarkdownStrategy", "ResponseStrategy", "SimpleResponseStrategy",
    "StreamingResponseStrategy", "StreamingStrategy", "StructuredResponseStrategy", "StructuredStrategy",
]
