"""Typed response and streaming transport models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .context import (
    Citation,
    PartialFailure,
    ResponseArtifact,
    ResponseAttachment,
    ResponseAttribute,
    OutputFormat,
)


class ResponseStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class ResponseMetrics:
    strategy_name: str = ""
    content_length: int = 0
    chunk_count: int = 0
    build_duration_seconds: float = 0.0


@dataclass(frozen=True)
class ResponseImage:
    image_id: str
    alt_text: str
    location: str | None = None


@dataclass(frozen=True)
class ResponseTable:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Response:
    """User-facing, transport-neutral result of response construction."""

    content: str
    output_format: OutputFormat
    response_id: str = ""
    status: ResponseStatus = ResponseStatus.COMPLETED
    is_partial: bool = False
    citations: tuple[Citation, ...] = ()
    images: tuple[ResponseImage, ...] = ()
    tables: tuple[ResponseTable, ...] = ()
    artifacts: tuple[ResponseArtifact, ...] = ()
    attachments: tuple[ResponseAttachment, ...] = ()
    partial_failures: tuple[PartialFailure, ...] = ()
    metadata: tuple[ResponseAttribute, ...] = ()
    metrics: ResponseMetrics = ResponseMetrics()


@dataclass(frozen=True)
class ResponseChunk:
    response_id: str
    sequence: int
    content: str
    is_final: bool = False


@dataclass(frozen=True)
class StreamingResponse:
    response: Response
    chunks: tuple[ResponseChunk, ...]

    def __iter__(self):
        return iter(self.chunks)
