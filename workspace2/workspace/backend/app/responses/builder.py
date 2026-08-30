"""Response Builder: the boundary from execution facts to user-facing output."""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import Sequence

from ..events.bus import EventBus
from ..events.model import (
    ResponseCompleted,
    ResponseFailed,
    ResponseFailedPayload,
    ResponsePayload,
    ResponseStarted,
)
from .context import ResponseContext
from .middleware import ResponseMiddlewarePipeline, ResponseMiddlewareRegistry
from .models import Response, ResponseChunk, ResponseMetrics, StreamingResponse
from .rendering import ResponseFormatter, ResponseRenderer
from .strategies import (
    ArtifactStrategy,
    MarkdownStrategy,
    ResponseStrategy,
    SimpleResponseStrategy,
    StreamingStrategy,
    StructuredStrategy,
)


class ResponseBuilder:
    """Builds responses only; it never invokes execution or planning layers."""

    def __init__(
        self,
        *,
        renderer: ResponseRenderer | None = None,
        formatter: ResponseFormatter | None = None,
        strategies: Sequence[ResponseStrategy] | None = None,
        middleware: ResponseMiddlewarePipeline | None = None,
        middleware_registry: ResponseMiddlewareRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        if middleware is not None and middleware_registry is not None:
            raise ValueError("Inject either response middleware or a registry, not both.")
        self._renderer = renderer or ResponseRenderer()
        self._formatter = formatter or ResponseFormatter()
        self._strategies = tuple(strategies or (
            ArtifactStrategy(),
            StreamingStrategy(),
            StructuredStrategy(),
            MarkdownStrategy(),
            SimpleResponseStrategy(),
        ))
        self._middleware = middleware
        self._middleware_registry = middleware_registry
        self._event_bus = event_bus

    def strategy_for(self, context: ResponseContext) -> ResponseStrategy:
        return next((item for item in self._strategies if item.supports(context)), SimpleResponseStrategy())

    def build(self, context: ResponseContext) -> Response:
        """Synchronous compatibility entry point for non-async callers."""
        return asyncio.run(self.build_async(context))

    async def build_async(self, context: ResponseContext) -> Response:
        self._publish(ResponseStarted(source="response_builder", payload=ResponsePayload(context.response_id, context.streaming_enabled), correlation_id=context.execution_context.correlation_id))
        try:
            pipeline = self._middleware_registry.snapshot() if self._middleware_registry is not None else (self._middleware or ResponseMiddlewarePipeline())
            started = time.monotonic()
            response = await pipeline.execute(context, self._build_with_strategy)
        except Exception as exc:
            self._publish(ResponseFailed(source="response_builder", payload=ResponseFailedPayload(context.response_id, type(exc).__name__, str(exc)), correlation_id=context.execution_context.correlation_id))
            raise
        strategy = self.strategy_for(context)
        response = replace(
            response,
            metrics=ResponseMetrics(strategy.name, len(response.content), response.metrics.chunk_count, time.monotonic() - started),
        )
        self._publish(ResponseCompleted(source="response_builder", payload=ResponsePayload(context.response_id, context.streaming_enabled), correlation_id=context.execution_context.correlation_id))
        return response

    def build_stream(self, context: ResponseContext, *, chunk_size: int = 256) -> StreamingResponse:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive.")
        response = self.build(replace(context, streaming_enabled=True))
        chunks = tuple(
            ResponseChunk(response.response_id, index, response.content[offset:offset + chunk_size], False)
            for index, offset in enumerate(range(0, len(response.content), chunk_size))
        )
        if not chunks:
            chunks = (ResponseChunk(response.response_id, 0, "", True),)
        else:
            chunks = (*chunks[:-1], replace(chunks[-1], is_final=True))
        response = replace(response, metrics=replace(response.metrics, chunk_count=len(chunks)))
        return StreamingResponse(response, chunks)

    async def _build_with_strategy(self, context: ResponseContext) -> Response:
        return self.strategy_for(context).build(context, self._renderer, self._formatter)

    def _publish(self, event: object) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)  # type: ignore[arg-type]
