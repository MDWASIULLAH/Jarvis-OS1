"""
brain/llm_interface.py

Pluggable interface to a local LLM. Ollama is the default target because
it's the simplest local setup (`ollama pull llama3.1:8b` + `ollama serve`),
but the same interface works for llama.cpp's server or LM Studio's
OpenAI-compatible endpoint -- just add another *Backend class below.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Iterator, Optional

import requests

from ..models import (
    LegacyLLMProviderAdapter,
    ModelCapability,
    ModelManager,
    ModelRequest,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
)


class LLMBackend(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def generate_stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        """A compatible streaming surface for clients that support incremental UI.

        Backends can override this for native streaming. The fallback remains
        useful for models and mocks that only expose a single response."""
        yield self.generate(prompt, system)


class OllamaBackend(LLMBackend):
    kind = "ollama"

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        payload = {"model": self.model, "prompt": prompt, "system": system or "", "stream": False}
        r = requests.post(f"{self.host}/api/generate", json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("response", "").strip()

    def generate_stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        payload = {"model": self.model, "prompt": prompt, "system": system or "", "stream": True}
        with requests.post(f"{self.host}/api/generate", json=payload, timeout=120, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                text = chunk.get("response", "")
                if text:
                    yield text


class MockBackend(LLMBackend):
    """Deterministic stand-in so the rest of the stack is testable without a
    GPU or a local model installed."""

    kind = "mock"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        return f"[mock response] I heard: {prompt[:200]}"


def get_default_backend() -> LLMBackend:
    """Prefers a real local model; otherwise the built-in reasoning engine.

    The old behaviour fell back to ``MockBackend``, which answered every
    question with "[mock response] I heard: ..." on any machine without
    Ollama installed. That is the single biggest reason a fresh clone looked
    broken, so the fallback is now a real (if simple) answer composer.
    """

    ollama = OllamaBackend()
    if ollama.is_available():
        return ollama
    from .local_engine import LocalReasoningBackend

    return LocalReasoningBackend()


class OpenAICompatibleBackend(LLMBackend):
    """Optional cloud or LAN model connector.

    Speaks the widely-used OpenAI-compatible chat-completions schema without
    naming a hosted provider, so it works equally for a real cloud endpoint
    or a local server (vLLM, LM Studio, text-generation-webui) exposing that
    same API for models like Qwen, DeepSeek, or Mistral. It is only enabled
    when the owner explicitly supplies an endpoint, a model, and
    `JARVIS_ALLOW_CLOUD=true` in the environment; local Ollama stays the
    default either way."""

    kind = "openai_compatible"

    def __init__(self, base_url: str, model: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if "openrouter" in self.base_url.lower():
            headers["HTTP-Referer"] = "https://jarvis.local"
            headers["X-Title"] = "JARVIS OS"
        return headers

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=3)
            return response.status_code < 500
        except requests.RequestException:
            return False

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        choices = response.json().get("choices", [])
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", "")).strip()

    def generate_stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        with requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={"model": self.model, "messages": messages, "stream": True},
            timeout=120,
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except Exception:
                    continue


#: Tasks answered by real tools (a calculator, the clock, the memory store,
#: an image endpoint) rather than by a language model. Routing one of these to
#: a cloud model would spend a request to produce a worse answer.
_DETERMINISTIC_TASKS = frozenset(
    {
        "math",
        "clock",
        "memory",
        "media",
        "system",
        "action",
        "weather",
        "currency",
        "news",
        "smalltalk",
    }
)


class ModelRouter:
    """Compatibility facade that delegates all LLM access to ModelManager."""

    def __init__(self, local: LLMBackend, cloud: Optional[LLMBackend] = None, allow_cloud: bool = False):
        self.local = local
        self.cloud = cloud
        self.allow_cloud = allow_cloud
        self.manager = ModelManager()
        self.manager.register_provider(
            self._metadata("local", local, ProviderKind.LOCAL, priority=100),
            lambda context: LegacyLLMProviderAdapter(local, self._metadata("local", local, ProviderKind.LOCAL, priority=100)),
        )
        # A request that reaches a partially configured local server must not
        # make the legacy API unusable.  This provider is ranked only after
        # the caller's requested local/cloud providers have failed.
        from .local_engine import LocalReasoningBackend
        fallback_backend = LocalReasoningBackend()
        self.manager.register_provider(
            self._metadata("local_fallback", fallback_backend, ProviderKind.EMBEDDED, priority=-100),
            lambda context: LegacyLLMProviderAdapter(
                fallback_backend,
                self._metadata("local_fallback", fallback_backend, ProviderKind.EMBEDDED, priority=-100),
            ),
        )
        if cloud is not None:
            self.manager.register_provider(
                self._metadata("cloud", cloud, ProviderKind.REMOTE, priority=10),
                lambda context: LegacyLLMProviderAdapter(cloud, self._metadata("cloud", cloud, ProviderKind.REMOTE, priority=10)),
            )

    def generate(self, prompt: str, system: Optional[str] = None, preference: str = "local") -> str:
        return self.manager.generate(self._request(prompt, system, preference)).content

    def generate_stream(self, prompt: str, system: Optional[str] = None, preference: str = "local") -> Iterator[str]:
        yield from (chunk.content for chunk in self.manager.stream_generate(self._request(prompt, system, preference)))

    def resolve_route(self, task: str = "general", requested: str = "auto") -> dict:
        """Pick the engine for one task and explain the choice.

        `requested` is what the caller asked for: "local", "cloud", or "auto".
        "auto" means "you decide": deterministic tasks (arithmetic, clock,
        memory) never need a language model, while free-form work (code,
        prose, translation) needs one that can actually write. Reporting the
        decision back matters as much as making it -- the UI shows a model
        name, and it should be the engine that ran, not the label a dropdown
        happened to be left on.
        """
        status = self.status()
        deterministic = task in _DETERMINISTIC_TASKS
        cloud_ready = bool(status["cloud_configured"] and status["cloud_allowed"])
        wants = (requested or "auto").lower()

        if wants == "cloud" and cloud_ready:
            return self._route("cloud", task, "requested")
        if wants == "local":
            # An explicit local request is honoured even when local cannot
            # write prose: privacy beats output quality when it was asked for.
            return self._route("local", task, "requested")
        if deterministic:
            return self._route("local", task, "deterministic task needs no language model")
        if status["generative_local"] and status["local_available"]:
            return self._route("local", task, "local model can generate")
        if cloud_ready:
            reason = "local engine cannot write free-form output" if not status["generative_local"] else "local model unavailable"
            return self._route("cloud", task, reason)
        return self._route("local", task, "no generative engine configured")

    def _route(self, provider: str, task: str, reason: str) -> dict:
        backend = self.cloud if provider == "cloud" else self.local
        return {
            "provider": provider,
            "task": task,
            "model": str(getattr(backend, "model", getattr(backend, "kind", provider))),
            "engine": str(getattr(backend, "kind", provider)),
            "reason": reason,
            "generative": provider == "cloud" or bool(self.status()["generative_local"]),
        }

    def generative_provider(self, requested: str = "auto") -> Optional[str]:
        """The provider that can actually write free-form text, or None.

        On most installs "local" is the deterministic reasoning engine: it
        composes answers out of retrieved evidence and never invents prose. Ask
        it to "write a function that reverses a string" and it returns a
        clarification template, which is correct behaviour for what it is.

        The bug this exists to fix: every caller passed `preference="local"`
        literally, and `_request` only routes to cloud when the caller asks for
        it by name. So configuring an OpenRouter key changed nothing -- the key
        was verified, reported as connected, and never used, and free-form
        requests kept returning the template. Resolving the provider by
        capability instead of by hardcoded name is what makes a configured key
        take effect.

        "auto" (now the API default) resolves by capability. An explicit
        "local" is honoured even when local cannot generate: choosing local is
        a privacy decision, and silently answering from the cloud would break
        it. Callers that want the upgrade ask for "auto".

        Returns "cloud", "local", or None when nothing can generate freely.
        """
        wants = (requested or "auto").lower()
        cloud_ready = self.allow_cloud and self.cloud is not None
        # An explicit cloud request wins, so the chat provider selector still works.
        if wants == "cloud" and cloud_ready:
            return "cloud"
        if self.status()["generative_local"]:
            return "local"
        if wants == "local":
            return None
        # Local cannot generate, but a key is configured and permitted: use it
        # rather than falling back to a template.
        return "cloud" if cloud_ready else None

    def status(self) -> dict:
        return {
            "default": "local",
            # `local_kind` lets callers tell a real generative model apart from
            # the deterministic built-in engine, which matters because only the
            # former should be asked to write free-form prose.
            "local_kind": getattr(self.local, "kind", "unknown"),
            "generative_local": getattr(self.local, "kind", "unknown") in {"ollama", "openai_compatible"},
            "local_available": self.manager.health("local").status is ProviderHealthStatus.HEALTHY,
            "cloud_configured": bool(self.cloud),
            "cloud_allowed": self.allow_cloud,
            "privacy": "Requests stay local unless the caller selects cloud and JARVIS_ALLOW_CLOUD is enabled.",
        }

    def _request(self, prompt: str, system: Optional[str], preference: str) -> ModelRequest:
        wants = (preference or "auto").lower()
        cloud_ready = self.allow_cloud and self.cloud is not None
        if wants == "cloud" and cloud_ready:
            preferred, fallback = ("cloud", "local"), ("local", "local_fallback")
        elif wants == "auto" and cloud_ready and not self.status()["generative_local"]:
            # Local is the deterministic engine, so free-form work goes to the
            # configured cloud model first and keeps local as the safety net.
            preferred, fallback = ("cloud", "local"), ("local", "local_fallback")
        elif wants == "auto" and cloud_ready:
            preferred, fallback = ("local", "cloud"), ("cloud", "local_fallback")
        else:
            preferred, fallback = ("local",), ("local_fallback",)
        return ModelRequest(prompt, system_prompt=system, preferred_provider_ids=preferred, fallback_provider_ids=fallback)

    @staticmethod
    def _metadata(provider_id: str, backend: LLMBackend, kind: ProviderKind, *, priority: int) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id=provider_id,
            display_name=provider_id.title(),
            model_name=str(getattr(backend, "model", getattr(backend, "kind", provider_id))),
            kind=kind,
            capabilities=(
                ModelCapability.CHAT,
                ModelCapability.CODING,
                ModelCapability.REASONING,
                ModelCapability.TRANSLATION,
                ModelCapability.TOKENIZATION,
                ModelCapability.STREAMING,
            ),
            priority=priority,
        )
