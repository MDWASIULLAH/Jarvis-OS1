"""Injectable response-middleware contracts, without response rendering logic."""

from __future__ import annotations

import inspect
import threading
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from .context import ResponseContext
from .models import Response

# Preserved import name from the infrastructure-preparation phase.
ResponseOutput = Response


@dataclass(frozen=True)
class ResponseError:
    error_type: str
    message: str


ResponseInvocation = Callable[[ResponseContext], Awaitable[ResponseOutput]]
ResolvedT = TypeVar("ResolvedT")


@runtime_checkable
class ResponseMiddleware(Protocol):
    """Independent hooks around the eventual response construction operation."""

    def before_response(self, context: ResponseContext) -> ResponseContext | Awaitable[ResponseContext]:
        """Prepare or replace the response context before construction."""

    def after_response(
        self,
        context: ResponseContext,
        response: ResponseOutput,
    ) -> ResponseOutput | Awaitable[ResponseOutput]:
        """Observe or replace a successful response output."""

    def error_response(
        self,
        context: ResponseContext,
        error: ResponseError,
    ) -> ResponseOutput | None | Awaitable[ResponseOutput | None]:
        """Legacy name for optionally recovering from a response-stage error."""

    def on_error(
        self,
        context: ResponseContext,
        error: ResponseError,
    ) -> ResponseOutput | None | Awaitable[ResponseOutput | None]:
        """Preferred error hook for response-stage recovery."""


class ResponseMiddlewarePipeline:
    """Immutable response middleware chain with deterministic hook ordering."""

    def __init__(self, middleware: Sequence[ResponseMiddleware] = ()) -> None:
        self._middleware = tuple(middleware)

    @property
    def middleware(self) -> tuple[ResponseMiddleware, ...]:
        return self._middleware

    def with_middleware(self, middleware: ResponseMiddleware) -> "ResponseMiddlewarePipeline":
        return ResponseMiddlewarePipeline((*self._middleware, middleware))

    async def execute(self, context: ResponseContext, invoke: ResponseInvocation) -> ResponseOutput:
        active_context = context
        entered: list[ResponseMiddleware] = []
        try:
            for item in self._middleware:
                active_context = await _resolve(item.before_response(active_context))
                entered.append(item)
            response = await invoke(active_context)
            for item in reversed(entered):
                response = await _resolve(item.after_response(active_context, response))
            return response
        except Exception as exc:
            error = ResponseError(type(exc).__name__, str(exc))
            for item in reversed(entered):
                handler = getattr(item, "on_error", None) or item.error_response
                recovered = await _resolve(handler(active_context, error))
                if recovered is not None:
                    return recovered
            raise


class ResponseMiddlewareRegistry:
    """Thread-safe, injectable registration point for a future Response Builder."""

    def __init__(self, middleware: Sequence[ResponseMiddleware] = ()) -> None:
        self._lock = threading.RLock()
        self._middleware = tuple(middleware)

    def register(self, middleware: ResponseMiddleware) -> None:
        with self._lock:
            self._middleware = (*self._middleware, middleware)

    def snapshot(self) -> ResponseMiddlewarePipeline:
        with self._lock:
            return ResponseMiddlewarePipeline(self._middleware)


async def _resolve(value: ResolvedT | Awaitable[ResolvedT]) -> ResolvedT:
    return await value if inspect.isawaitable(value) else value
