"""Composable, capability-independent middleware for execution steps."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, TypeVar, runtime_checkable

from ..capabilities.contracts import CapabilityResult
from .context import ExecutionContext


MaybeAwaitable = TypeVar("MaybeAwaitable")
CapabilityInvocation = Callable[[ExecutionContext], Awaitable[CapabilityResult]]


@runtime_checkable
class ExecutionMiddleware(Protocol):
    """A boundary around one capability invocation.

    Entry hooks run in registration order; exit hooks run in reverse order,
    matching normal nested middleware semantics.  Implementations may return
    either a direct value or an awaitable, making simple in-process policies
    inexpensive while retaining an async-ready extension point.
    """

    def before_execute(self, context: ExecutionContext) -> ExecutionContext | Awaitable[ExecutionContext]:
        """Prepare or replace the context before the capability is invoked."""

    def after_execute(
        self,
        context: ExecutionContext,
        result: CapabilityResult,
    ) -> CapabilityResult | Awaitable[CapabilityResult]:
        """Observe or replace a successful capability result."""


class MiddlewarePipeline:
    """Immutable middleware chain that propagates hook errors to its caller."""

    def __init__(self, middleware: Sequence[ExecutionMiddleware] = ()) -> None:
        self._middleware = tuple(middleware)

    @property
    def middleware(self) -> tuple[ExecutionMiddleware, ...]:
        return self._middleware

    def with_middleware(self, middleware: ExecutionMiddleware) -> "MiddlewarePipeline":
        return MiddlewarePipeline((*self._middleware, middleware))

    async def execute(self, context: ExecutionContext, invoke: CapabilityInvocation) -> CapabilityResult:
        active_context = context
        entered: list[ExecutionMiddleware] = []
        for item in self._middleware:
            active_context = await _resolve(item.before_execute(active_context))
            entered.append(item)
        result = await invoke(active_context)
        for item in reversed(entered):
            result = await _resolve(item.after_execute(active_context, result))
        return result


async def _resolve(value: MaybeAwaitable | Awaitable[MaybeAwaitable]) -> MaybeAwaitable:
    return await value if inspect.isawaitable(value) else value
