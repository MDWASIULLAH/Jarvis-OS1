"""Stable response-boundary contracts for a future Response Builder."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from ..execution.context import ExecutionContext
from ..execution.models import ExecutionResult, FailureReport


class OutputFormat(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class Tone(str, Enum):
    NEUTRAL = "neutral"
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    CONVERSATIONAL = "conversational"


@dataclass(frozen=True)
class ResponseAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class ConversationContext:
    conversation_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None


@dataclass(frozen=True)
class UserPreferences:
    preferred_format: OutputFormat | None = None
    language: str | None = None
    tone: Tone | None = None
    stream_responses: bool | None = None


@dataclass(frozen=True)
class Citation:
    citation_id: str
    label: str
    source: str
    url: str | None = None


@dataclass(frozen=True)
class ResponseAttachment:
    attachment_id: str
    name: str
    media_type: str
    location: str | None = None


# Concise public name for response consumers; the original name remains valid.
Attachment = ResponseAttachment


@dataclass(frozen=True)
class ResponseArtifact:
    artifact_id: str
    name: str
    artifact_type: str
    location: str | None = None


@dataclass(frozen=True)
class PartialFailure:
    step_id: str | None
    capability_id: str | None
    error_type: str
    message: str

    @classmethod
    def from_failure(cls, failure: FailureReport) -> "PartialFailure":
        return cls(failure.step_id, failure.capability_id, failure.error_type, failure.message)


@dataclass(frozen=True)
class ResponseTelemetry:
    correlation_id: str
    attributes: tuple[ResponseAttribute, ...] = ()


@dataclass(frozen=True, kw_only=True)
class ResponseContext:
    """Immutable request state supplied to the future Response Builder.

    The execution contracts are retained by reference, while response-facing
    fields are immutable tuples and enums.  New optional fields can be added
    without changing the Builder's single-argument boundary.
    """

    response_id: str
    execution_result: ExecutionResult
    execution_context: ExecutionContext
    conversation_context: ConversationContext | None = None
    user_preferences: UserPreferences = field(default_factory=UserPreferences)
    output_format: OutputFormat = OutputFormat.MARKDOWN
    streaming_enabled: bool = False
    language: str = "en"
    tone: Tone = Tone.NEUTRAL
    citations: tuple[Citation, ...] = ()
    attachments: tuple[ResponseAttachment, ...] = ()
    artifacts: tuple[ResponseArtifact, ...] = ()
    partial_failures: tuple[PartialFailure, ...] = ()
    telemetry: ResponseTelemetry | None = None
    metadata: tuple[ResponseAttribute, ...] = ()

    @classmethod
    def create(
        cls,
        execution_result: ExecutionResult,
        execution_context: ExecutionContext,
        *,
        response_id: str | None = None,
        conversation_context: ConversationContext | None = None,
        user_preferences: UserPreferences | None = None,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        streaming_enabled: bool = False,
        language: str = "en",
        tone: Tone = Tone.NEUTRAL,
        citations: tuple[Citation, ...] = (),
        attachments: tuple[ResponseAttachment, ...] = (),
        artifacts: tuple[ResponseArtifact, ...] = (),
        partial_failures: tuple[PartialFailure, ...] | None = None,
        telemetry: ResponseTelemetry | None = None,
        metadata: tuple[ResponseAttribute, ...] = (),
    ) -> "ResponseContext":
        failures = partial_failures
        if failures is None:
            failures = tuple(PartialFailure.from_failure(item) for item in execution_result.failures)
        conversation = conversation_context or ConversationContext(
            execution_context.conversation_id,
            execution_context.session_id,
            execution_context.user_id,
        )
        return cls(
            response_id=response_id or str(uuid.uuid4()),
            execution_result=execution_result,
            execution_context=execution_context,
            conversation_context=conversation,
            user_preferences=user_preferences or UserPreferences(),
            output_format=output_format,
            streaming_enabled=streaming_enabled,
            language=language,
            tone=tone,
            citations=citations,
            attachments=attachments,
            artifacts=artifacts,
            partial_failures=failures,
            telemetry=telemetry or ResponseTelemetry(execution_context.correlation_id),
            metadata=metadata,
        )
