"""Privacy-conscious manifest registry; plugins are opt-in, never auto-installed."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PluginManifest:
    identifier: str
    name: str
    category: str
    requires_oauth: bool = False
    local_only: bool = False


_BUILT_INS = (
    PluginManifest("github", "GitHub", "developer", requires_oauth=True),
    PluginManifest("gitlab", "GitLab", "developer", requires_oauth=True),
    PluginManifest("google-drive", "Google Drive", "productivity", requires_oauth=True),
    PluginManifest("google-calendar", "Google Calendar", "productivity", requires_oauth=True),
    PluginManifest("outlook", "Outlook", "productivity", requires_oauth=True),
    PluginManifest("notion", "Notion", "productivity", requires_oauth=True),
    PluginManifest("onedrive", "OneDrive", "storage", requires_oauth=True),
    PluginManifest("dropbox", "Dropbox", "storage", requires_oauth=True),
    PluginManifest("slack", "Slack", "communication", requires_oauth=True),
    PluginManifest("teams", "Microsoft Teams", "communication", requires_oauth=True),
    PluginManifest("discord", "Discord", "communication", requires_oauth=True),
    PluginManifest("figma", "Figma", "design", requires_oauth=True),
    PluginManifest("canva", "Canva", "design", requires_oauth=True),
    PluginManifest("spotify", "Spotify", "media", requires_oauth=True),
    PluginManifest("browser", "Local Browser Automation", "automation", local_only=True),
    PluginManifest("vscode", "VS Code", "developer", local_only=True),
    PluginManifest("jetbrains", "JetBrains IDEs", "developer", local_only=True),
)


class PluginRegistry:
    def __init__(self):
        self._enabled: set[str] = set()

    def available(self) -> list[dict]:
        return [asdict(plugin) | {"enabled": plugin.identifier in self._enabled} for plugin in _BUILT_INS]

    def enable(self, identifier: str) -> dict | None:
        plugin = next((item for item in _BUILT_INS if item.identifier == identifier), None)
        if plugin is None:
            return None
        self._enabled.add(identifier)
        return asdict(plugin) | {"enabled": True, "oauth_connection_required": plugin.requires_oauth}
