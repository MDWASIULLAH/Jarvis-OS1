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


class ModelRouter:
    """Routes a request to an explicitly chosen local or opt-in cloud model.

    This is deliberately simpler than "auto-pick the best of five providers":
    it picks between exactly one local backend and (optionally) one opt-in
    cloud/LAN backend, based on what the caller asks for. That's an honest
    version of "model routing" that's actually verifiable, rather than a
    claim about automatically judging which of several unrelated models is
    smartest for a given task."""

    def __init__(self, local: LLMBackend, cloud: Optional[LLMBackend] = None, allow_cloud: bool = False):
        self.local = local
        self.cloud = cloud
        self.allow_cloud = allow_cloud

    def generate(self, prompt: str, system: Optional[str] = None, preference: str = "local") -> str:
        wants_cloud = preference.lower() == "cloud"
        if wants_cloud and self.allow_cloud and self.cloud and self.cloud.is_available():
            return self.cloud.generate(prompt, system)
        return self.local.generate(prompt, system)

    def generate_stream(self, prompt: str, system: Optional[str] = None, preference: str = "local") -> Iterator[str]:
        wants_cloud = preference.lower() == "cloud"
        backend = self.cloud if wants_cloud and self.allow_cloud and self.cloud and self.cloud.is_available() else self.local
        yield from backend.generate_stream(prompt, system)

    def status(self) -> dict:
        return {
            "default": "local",
            # `local_kind` lets callers tell a real generative model apart from
            # the deterministic built-in engine, which matters because only the
            # former should be asked to write free-form prose.
            "local_kind": getattr(self.local, "kind", "unknown"),
            "generative_local": getattr(self.local, "kind", "unknown") in {"ollama", "openai_compatible"},
            "local_available": self.local.is_available(),
            "cloud_configured": bool(self.cloud),
            "cloud_allowed": self.allow_cloud,
            "privacy": "Requests stay local unless the caller selects cloud and JARVIS_ALLOW_CLOUD is enabled.",
        }
