"""Declarative registration of the existing JARVIS capability modules."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CapabilityContext, CapabilityMetadata
from .legacy_adapter import LegacyModuleCapability
from .registry import CapabilityRegistry


@dataclass(frozen=True)
class _LegacySpec:
    metadata: CapabilityMetadata
    module_path: str
    service_name: str | None = None
    health_probe: str | None = None


_SPECS: tuple[_LegacySpec, ...] = (
    _LegacySpec(CapabilityMetadata("app_launcher", "Launch approved local applications, paths, and websites.", "Application Launcher", "System", supported_intents=("action.open_app", "action.web_open"), permissions=("app_open",), tags=("desktop",), priority=90), "app.capabilities.app_launcher", health_probe="status"),
    _LegacySpec(CapabilityMetadata("chat_platforms", "Communicate through supported chat platforms.", permissions=("external_message",), tags=("communication",), priority=40), "app.capabilities.chat_platforms"),
    _LegacySpec(CapabilityMetadata("code_execution", "Execute Python snippets in the current local execution environment.", "Code Runner", "Developer", supported_intents=("task.code", "info.math"), permissions=("code_execute",), tags=("developer",), legacy_ids=("code_runner",), priority=80), "app.capabilities.code_executor"),
    _LegacySpec(CapabilityMetadata("desktop_automation", "Perform approved desktop automation operations.", "Desktop Automation", "System", permissions=("desktop_control",), dependencies=("desktop",), tags=("desktop",), legacy_ids=("desktop_automation",), priority=70), "app.capabilities.desktop_automation", service_name="desktop"),
    _LegacySpec(CapabilityMetadata("document_reader", "Extract text from supported document formats.", supported_intents=("doc.read",), permissions=("file_read",), tags=("documents",), priority=60), "app.capabilities.document_reader"),
    _LegacySpec(CapabilityMetadata("document_writer", "Create Word, PowerPoint, and spreadsheet documents.", permissions=("file_write",), tags=("documents",), priority=60), "app.capabilities.document_writer"),
    _LegacySpec(CapabilityMetadata("email", "Draft and send email through the configured provider.", permissions=("email_send",), dependencies=("email",), tags=("communication",), priority=80), "app.capabilities.email_module", service_name="email"),
    _LegacySpec(CapabilityMetadata("fun_space", "Retrieve astronomy and technology information.", supported_intents=("info.factual",), permissions=("network",), tags=("knowledge",), priority=25), "app.capabilities.fun_and_space"),
    _LegacySpec(CapabilityMetadata("github", "Read repository metadata and issues from GitHub.", permissions=("network",), tags=("developer",), priority=45), "app.capabilities.github_client"),
    _LegacySpec(CapabilityMetadata("image_pipeline", "Search, retrieve, generate, and cache images.", "Image Pipeline", "Media", supported_intents=("media.image_search", "media.image_generate"), permissions=("network", "media_write"), tags=("media",), legacy_ids=("image_generation", "image_search"), priority=85), "app.capabilities.image_pipeline"),
    _LegacySpec(CapabilityMetadata("knowledge_apis", "Retrieve factual and reference material from public sources.", "Multi-Source Knowledge", "Knowledge", supported_intents=("info.factual", "info.definition"), permissions=("network",), tags=("knowledge",), legacy_ids=("multi_source_knowledge",), priority=75), "app.capabilities.knowledge_apis"),
    _LegacySpec(CapabilityMetadata("location", "Resolve location, routes, and IP information.", supported_intents=("info.weather",), permissions=("network",), dependencies=("location",), tags=("knowledge",), priority=55), "app.capabilities.location_services", service_name="location"),
    _LegacySpec(CapabilityMetadata("personal_memory", "Remember and recall facts you share.", "Personal Memory", "Knowledge", permissions=("memory_write",), dependencies=("memory",), tags=("knowledge",), legacy_ids=("memory",), priority=65), "app.memory.memory_store", service_name="memory"),
    _LegacySpec(CapabilityMetadata("media_store", "Persist and retrieve generated media artifacts.", permissions=("media_write",), dependencies=("media",), tags=("media",), priority=50), "app.capabilities.media_store", service_name="media"),
    _LegacySpec(CapabilityMetadata("news", "Retrieve headlines from configured or public news providers.", "News", "Information", supported_intents=("info.news",), permissions=("network",), dependencies=("news",), tags=("knowledge",), legacy_ids=("news",), priority=70), "app.capabilities.news_module", service_name="news"),
    _LegacySpec(CapabilityMetadata("smart_home", "Control configured smart-home services.", permissions=("smart_home_control",), tags=("automation",), priority=65), "app.capabilities.smart_home"),
    _LegacySpec(CapabilityMetadata("system_control", "Read or request approved local system controls.", supported_intents=("action.system_control",), permissions=("system_control",), tags=("desktop",), priority=65), "app.capabilities.system_control"),
    _LegacySpec(CapabilityMetadata("deterministic_skills", "Evaluate deterministic math and time operations.", "Math & Time", "Utilities", supported_intents=("info.math", "info.time"), permissions=(), tags=("utilities",), legacy_ids=("math", "time_date"), priority=75), "app.brain.skills"),
    _LegacySpec(CapabilityMetadata("translation_currency", "Translate text and convert currencies.", "Translation & Currency", "Language", supported_intents=("info.translate", "info.currency"), permissions=("network",), tags=("language",), legacy_ids=("translation", "currency"), priority=60), "app.capabilities.translate_currency"),
    _LegacySpec(CapabilityMetadata("vision_ocr", "Extract text from user-provided images.", supported_intents=("vision.analyze",), permissions=("file_read",), tags=("vision",), priority=75), "app.capabilities.vision_ocr", health_probe="ocr_available"),
    _LegacySpec(CapabilityMetadata("voice", "Transcribe audio and synthesize local speech.", "Voice", "Interaction", permissions=("audio_input", "audio_output"), tags=("voice",), legacy_ids=("voice_tts", "speech_stt"), priority=50), "app.capabilities.voice_pipeline"),
    _LegacySpec(CapabilityMetadata("weather", "Retrieve current weather conditions.", "Weather", "Information", supported_intents=("info.weather",), permissions=("network",), dependencies=("weather",), tags=("knowledge",), legacy_ids=("weather",), priority=70), "app.capabilities.weather_module", service_name="weather"),
    _LegacySpec(CapabilityMetadata("web_research", "Search, read, and download public web content.", "Web Browsing", "Knowledge", supported_intents=("web.browse", "info.factual"), permissions=("network",), tags=("knowledge",), legacy_ids=("web_browse",), priority=85), "app.capabilities.web_research"),
    _LegacySpec(CapabilityMetadata("youtube", "Search YouTube videos through a configured provider.", supported_intents=("media.video_search",), permissions=("network",), tags=("media",), priority=45), "app.capabilities.youtube_client"),
)


def register_builtin_capabilities(registry: CapabilityRegistry) -> None:
    """Register every existing capability as a lazy compatibility adapter."""
    for spec in _SPECS:
        registry.register(
            spec.metadata,
            lambda context, spec=spec: LegacyModuleCapability(
                spec.metadata,
                spec.module_path,
                service_name=spec.service_name,
                health_probe=spec.health_probe,
            ),
        )


def build_builtin_registry(context: CapabilityContext | None = None) -> CapabilityRegistry:
    """Build a registry for tests or embedded callers without importing providers."""
    registry = CapabilityRegistry()
    register_builtin_capabilities(registry)
    registry.initialize(context or CapabilityContext())
    return registry
