"""
connectors/registry.py v2

Extended catalog of external services JARVIS can connect to.
Supports: Gmail, Drive, Calendar, GitHub, GitLab, Notion, Slack, Discord,
Dropbox, OneDrive, Spotify, Supabase, Firebase, AWS, Azure, Docker,
Jira, Linear, Trello, YouTube, LinkedIn, Reddit, HuggingFace, OpenRouter,
OpenAI, Anthropic, Gemini, Ollama, Qwen, DeepSeek, and more.

New additions: Outlook, Google Maps, Canva, WhatsApp Business.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(frozen=True)
class ConnectorField:
    key: str
    label: str
    placeholder: str = ""
    secret: bool = False
    required: bool = True
    help: str = ""
    kind: Literal["text", "password", "url", "email", "number"] = "text"


@dataclass(frozen=True)
class ConnectorSpec:
    id: str
    name: str
    category: str
    summary: str
    docs_url: str
    fields: tuple[ConnectorField, ...]
    note: str = ""


CATALOG: tuple[ConnectorSpec, ...] = (
    ConnectorSpec(
        id="gmail", name="Gmail", category="Email",
        summary="Read, draft, and send emails.",
        docs_url="https://support.google.com/accounts/answer/185833",
        note="Use a Google App Password. Requires 2-step verification.",
        fields=(
            ConnectorField(key="address", label="Gmail address", placeholder="you@gmail.com", kind="email"),
            ConnectorField(key="app_password", label="App password", placeholder="16-character app password", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="outlook", name="Outlook", category="Email",
        summary="Read, draft, and send emails via Microsoft Graph.",
        docs_url="https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps",
        note="Register an Azure AD app with Mail.Send and Mail.Read delegated permissions.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="Azure AD app client ID"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="Azure AD app secret", secret=True, kind="password"),
            ConnectorField(key="tenant_id", label="Tenant ID", placeholder="common", required=False),
            ConnectorField(key="email", label="Email address", placeholder="you@outlook.com", kind="email"),
            ConnectorField(key="refresh_token", label="Refresh token", placeholder="OAuth refresh token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="google_drive", name="Google Drive", category="Productivity",
        summary="Search, read, and manage Drive files.",
        docs_url="https://console.cloud.google.com/apis/credentials",
        note="Enable the Google Drive API. Use OAuth 2.0 credentials.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="OAuth client ID", secret=True, kind="password"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="OAuth client secret", secret=True, kind="password"),
            ConnectorField(key="refresh_token", label="Refresh Token", placeholder="OAuth refresh token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="google_calendar", name="Google Calendar", category="Productivity",
        summary="Read and create calendar events.",
        docs_url="https://console.cloud.google.com/apis/credentials",
        note="Enable the Google Calendar API.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="OAuth client ID", secret=True, kind="password"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="OAuth client secret", secret=True, kind="password"),
            ConnectorField(key="refresh_token", label="Refresh Token", placeholder="OAuth refresh token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="google_docs", name="Google Docs", category="Productivity",
        summary="Read and create Google Docs.",
        docs_url="https://console.cloud.google.com/apis/credentials",
        note="Enable Google Docs API.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="OAuth client ID", secret=True, kind="password"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="OAuth client secret", secret=True, kind="password"),
            ConnectorField(key="refresh_token", label="Refresh Token", placeholder="OAuth refresh token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="google_maps", name="Google Maps", category="Data",
        summary="Geocoding, directions, places search.",
        docs_url="https://console.cloud.google.com/google/maps-apis/credentials",
        note="Enable Maps JavaScript API and Geocoding API.",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="AIza...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="notion", name="Notion", category="Productivity",
        summary="Read and write Notion pages and databases.",
        docs_url="https://developers.notion.com/docs/create-a-notion-integration",
        note="Create an internal integration and share pages with it.",
        fields=(
            ConnectorField(key="api_key", label="Integration token", placeholder="secret_...", secret=True, kind="password"),
            ConnectorField(key="default_db", label="Default database ID", placeholder="database ID", required=False),
        ),
    ),
    ConnectorSpec(
        id="github", name="GitHub", category="Developer",
        summary="Read repos, commits, issues, and PRs.",
        docs_url="https://github.com/settings/tokens",
        note="Classic token with repo scope reads private repos.",
        fields=(
            ConnectorField(key="token", label="Personal access token", placeholder="ghp_...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="gitlab", name="GitLab", category="Developer",
        summary="Read repos, merge requests, and CI pipelines.",
        docs_url="https://gitlab.com/-/user_settings/personal_access_tokens",
        note="Token with api scope; self-managed instance supported.",
        fields=(
            ConnectorField(key="base_url", label="Instance URL", placeholder="https://gitlab.com", kind="url", required=False),
            ConnectorField(key="token", label="Personal access token", placeholder="glpat-...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="docker", name="Docker", category="Developer",
        summary="Manage containers, images, and volumes.",
        docs_url="https://docs.docker.com/engine/api/",
        note="Docker socket must be accessible. Runs locally.",
        fields=(
            ConnectorField(key="socket_path", label="Socket path", placeholder="/var/run/docker.sock", required=False),
        ),
    ),
    ConnectorSpec(
        id="supabase", name="Supabase", category="Developer",
        summary="Query databases, manage auth, and storage.",
        docs_url="https://supabase.com/dashboard/project/_/settings/api",
        fields=(
            ConnectorField(key="url", label="Project URL", placeholder="https://xxx.supabase.co", kind="url"),
            ConnectorField(key="anon_key", label="Anon/Public key", placeholder="eyJ...", secret=True, kind="password"),
            ConnectorField(key="service_role_key", label="Service role key", placeholder="eyJ...", secret=True, kind="password", required=False),
        ),
    ),
    ConnectorSpec(
        id="firebase", name="Firebase", category="Developer",
        summary="Access Firestore, Auth, and Storage.",
        docs_url="https://console.firebase.google.com/project/_/settings/serviceaccounts/adminsdk",
        fields=(
            ConnectorField(key="project_id", label="Project ID", placeholder="my-project"),
            ConnectorField(key="private_key", label="Private key", placeholder="-----BEGIN PRIVATE KEY-----...", secret=True, kind="password"),
            ConnectorField(key="client_email", label="Client email", placeholder="firebase-adminsdk@...", kind="text"),
        ),
    ),
    ConnectorSpec(
        id="vercel", name="Vercel", category="Developer",
        summary="Deploy projects, manage domains and env vars.",
        docs_url="https://vercel.com/account/tokens",
        fields=(
            ConnectorField(key="token", label="Access token", placeholder="vercel_token", secret=True, kind="password"),
            ConnectorField(key="team_id", label="Team ID", placeholder="team_...", required=False),
        ),
    ),
    ConnectorSpec(
        id="cloudflare", name="Cloudflare", category="Developer",
        summary="Manage Workers, Pages, DNS, and R2 storage.",
        docs_url="https://dash.cloudflare.com/profile/api-tokens",
        fields=(
            ConnectorField(key="api_token", label="API token", placeholder="Cloudflare API token", secret=True, kind="password"),
            ConnectorField(key="account_id", label="Account ID", placeholder="account ID", required=False),
        ),
    ),
    ConnectorSpec(
        id="slack", name="Slack", category="Messaging",
        summary="Post messages and read channels.",
        docs_url="https://api.slack.com/apps",
        note="Bot token with chat:write scope.",
        fields=(
            ConnectorField(key="bot_token", label="Bot token", placeholder="xoxb-...", secret=True, kind="password"),
            ConnectorField(key="default_channel", label="Default channel", placeholder="#general", required=False),
        ),
    ),
    ConnectorSpec(
        id="discord", name="Discord", category="Messaging",
        summary="Post messages to Discord channels via webhook or bot.",
        docs_url="https://discord.com/developers/applications",
        fields=(
            ConnectorField(key="bot_token", label="Bot token", placeholder="Bot token", secret=True, kind="password"),
            ConnectorField(key="webhook_url", label="Webhook URL", placeholder="https://discord.com/api/webhooks/...", kind="url", required=False),
        ),
    ),
    ConnectorSpec(
        id="telegram", name="Telegram", category="Messaging",
        summary="Send and receive messages through a bot with full remote control.",
        docs_url="https://core.telegram.org/bots",
        fields=(
            ConnectorField(key="bot_token", label="Bot token", placeholder="123456:ABC-DEF...", secret=True, kind="password"),
            ConnectorField(key="chat_id", label="Default chat ID", placeholder="123456789", required=False, kind="number"),
        ),
    ),
    ConnectorSpec(
        id="whatsapp", name="WhatsApp Business", category="Messaging",
        summary="Send messages and files via WhatsApp Cloud API (requires Meta Business account).",
        docs_url="https://developers.facebook.com/docs/whatsapp/cloud-api",
        note="Requires Meta Business verification, phone number ID, and access token. Not compatible with personal WhatsApp.",
        fields=(
            ConnectorField(key="access_token", label="Access token", placeholder="EAA...", secret=True, kind="password"),
            ConnectorField(key="phone_number_id", label="Phone number ID", placeholder="123456789..."),
        ),
    ),
    ConnectorSpec(
        id="jira", name="Jira", category="Project Management",
        summary="Read, create, and update issues.",
        docs_url="https://id.atlassian.com/manage-profile/security/api-tokens",
        fields=(
            ConnectorField(key="domain", label="Domain", placeholder="your-domain.atlassian.net", kind="url"),
            ConnectorField(key="email", label="Email", placeholder="you@example.com", kind="email"),
            ConnectorField(key="api_token", label="API token", placeholder="ATATT...", secret=True, kind="password"),
            ConnectorField(key="project_key", label="Default project key", placeholder="PROJ", required=False),
        ),
    ),
    ConnectorSpec(
        id="linear", name="Linear", category="Project Management",
        summary="Read and create issues in Linear.",
        docs_url="https://linear.app/settings/api",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="lin_api_...", secret=True, kind="password"),
            ConnectorField(key="team_id", label="Team ID", placeholder="team identifier", required=False),
        ),
    ),
    ConnectorSpec(
        id="trello", name="Trello", category="Project Management",
        summary="Manage boards, lists, and cards.",
        docs_url="https://trello.com/power-ups/admin",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="Trello API key"),
            ConnectorField(key="api_token", label="API token", placeholder="Trello token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="youtube", name="YouTube", category="Media",
        summary="Search videos and read channel details.",
        docs_url="https://console.cloud.google.com/apis/credentials",
        note="Enable YouTube Data API v3.",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="AIza...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="spotify", name="Spotify", category="Media",
        summary="Control playback, search music, and manage playlists.",
        docs_url="https://developer.spotify.com/dashboard",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="Spotify client ID"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="Spotify client secret", secret=True, kind="password"),
            ConnectorField(key="refresh_token", label="Refresh token", placeholder="OAuth refresh token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="openai", name="OpenAI", category="AI",
        summary="GPT-4, GPT-4o, DALL-E, Whisper, Embeddings.",
        docs_url="https://platform.openai.com/api-keys",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="sk-...", secret=True, kind="password"),
            ConnectorField(key="org_id", label="Organization ID", placeholder="org-...", required=False),
        ),
    ),
    ConnectorSpec(
        id="anthropic", name="Anthropic", category="AI",
        summary="Claude models for reasoning and coding.",
        docs_url="https://console.anthropic.com/settings/keys",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="sk-ant-...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="gemini", name="Google Gemini", category="AI",
        summary="Gemini models for multimodal AI.",
        docs_url="https://aistudio.google.com/apikey",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="AIza...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="openrouter", name="OpenRouter", category="AI",
        summary="Access 200+ models through a single API.",
        docs_url="https://openrouter.ai/keys",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="sk-or-...", secret=True, kind="password"),
            ConnectorField(key="model", label="Model", placeholder="openai/gpt-4o-mini", required=False),
        ),
    ),
    ConnectorSpec(
        id="ollama", name="Ollama", category="AI",
        summary="Run local LLMs: Llama, Mistral, Qwen, DeepSeek, Gemma.",
        docs_url="https://ollama.com/",
        note="Already used by default -- configure here for a remote instance.",
        fields=(
            ConnectorField(key="host", label="Host URL", placeholder="http://localhost:11434", kind="url", required=False),
            ConnectorField(key="model", label="Default model", placeholder="llama3.1:8b", required=False),
        ),
    ),
    ConnectorSpec(
        id="huggingface", name="HuggingFace", category="AI",
        summary="Access models, datasets, and inference endpoints.",
        docs_url="https://huggingface.co/settings/tokens",
        fields=(
            ConnectorField(key="api_token", label="API token", placeholder="hf_...", secret=True, kind="password"),
            ConnectorField(key="inference_endpoint", label="Inference endpoint URL", placeholder="https://api-inference.huggingface.co/models/...", kind="url", required=False),
        ),
    ),
    ConnectorSpec(
        id="aws", name="AWS", category="Cloud",
        summary="Access S3, Lambda, Bedrock, and other AWS services.",
        docs_url="https://console.aws.amazon.com/iam",
        fields=(
            ConnectorField(key="access_key_id", label="Access key ID", placeholder="AKIA..."),
            ConnectorField(key="secret_access_key", label="Secret access key", placeholder="secret key", secret=True, kind="password"),
            ConnectorField(key="region", label="Region", placeholder="us-east-1", required=False),
        ),
    ),
    ConnectorSpec(
        id="azure", name="Azure", category="Cloud",
        summary="Access Azure OpenAI, Blob Storage, and other services.",
        docs_url="https://portal.azure.com/",
        fields=(
            ConnectorField(key="subscription_id", label="Subscription ID", placeholder="subscription ID"),
            ConnectorField(key="tenant_id", label="Tenant ID", placeholder="tenant ID"),
            ConnectorField(key="client_id", label="Client ID", placeholder="client ID"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="client secret", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="dropbox", name="Dropbox", category="Storage",
        summary="Read, write, and manage Dropbox files.",
        docs_url="https://www.dropbox.com/developers/apps",
        fields=(
            ConnectorField(key="access_token", label="Access token", placeholder="sl.bt-...", secret=True, kind="password"),
            ConnectorField(key="app_key", label="App key", placeholder="Dropbox app key", required=False),
        ),
    ),
    ConnectorSpec(
        id="onedrive", name="OneDrive", category="Storage",
        summary="Read, write, and manage OneDrive files.",
        docs_url="https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade",
        note="Microsoft Graph API. Requires Azure AD app registration.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="Azure AD app client ID"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="client secret", secret=True, kind="password"),
            ConnectorField(key="refresh_token", label="Refresh token", placeholder="OAuth refresh token", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="openweather", name="OpenWeatherMap", category="Data",
        summary="Richer forecasts than the built-in Open-Meteo.",
        docs_url="https://home.openweathermap.org/api_keys",
        note="Weather already works without this.",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="OpenWeatherMap key", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="newsapi", name="NewsAPI", category="Data",
        summary="Headlines by category and keyword.",
        docs_url="https://newsapi.org/register",
        note="News already works without this, using RSS feeds.",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="NewsAPI key", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="figma", name="Figma", category="Design",
        summary="Access Figma files, components, and design tokens.",
        docs_url="https://www.figma.com/developers/api#access-tokens",
        fields=(
            ConnectorField(key="access_token", label="Personal access token", placeholder="figd_...", secret=True, kind="password"),
            ConnectorField(key="file_key", label="Default file key", placeholder="file key from URL", required=False),
        ),
    ),
    ConnectorSpec(
        id="canva", name="Canva", category="Design",
        summary="Access Canva designs and templates.",
        docs_url="https://www.canva.com/developers/",
        note="Requires a Canva Developer account and API key.",
        fields=(
            ConnectorField(key="api_key", label="API key", placeholder="Canva API key", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="home_assistant", name="Home Assistant", category="Smart Home",
        summary="Control lights, switches, and scenes.",
        docs_url="https://www.home-assistant.io/docs/authentication/",
        note="Create a long-lived access token on your HA profile page.",
        fields=(
            ConnectorField(key="base_url", label="Base URL", placeholder="http://homeassistant.local:8123", kind="url"),
            ConnectorField(key="token", label="Long-lived token", placeholder="eyJ...", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="linkedin", name="LinkedIn", category="Social",
        summary="Access LinkedIn profile and company data.",
        docs_url="https://www.linkedin.com/developers/apps",
        note="Requires LinkedIn App with appropriate API products.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="LinkedIn client ID"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="client secret", secret=True, kind="password"),
            ConnectorField(key="access_token", label="Access token", placeholder="OAuth access token", secret=True, kind="password", required=False),
        ),
    ),
    ConnectorSpec(
        id="reddit", name="Reddit", category="Social",
        summary="Read subreddits, posts, and comments.",
        docs_url="https://www.reddit.com/prefs/apps",
        note="Create a 'script' app to get credentials.",
        fields=(
            ConnectorField(key="client_id", label="Client ID", placeholder="Reddit app client ID"),
            ConnectorField(key="client_secret", label="Client Secret", placeholder="app secret", secret=True, kind="password"),
            ConnectorField(key="username", label="Reddit username", placeholder="u/username"),
            ConnectorField(key="password", label="Reddit password", placeholder="account password", secret=True, kind="password"),
        ),
    ),
    ConnectorSpec(
        id="cloud_llm", name="Cloud LLM", category="AI",
        summary="Fall back to a hosted model when local is unavailable.",
        docs_url="https://platform.openai.com/api-keys",
        note="JARVIS prefers local Ollama; this is fallback.",
        fields=(
            ConnectorField(key="base_url", label="Base URL", placeholder="https://api.openai.com/v1", kind="url"),
            ConnectorField(key="api_key", label="API key", placeholder="sk-...", secret=True, kind="password"),
            ConnectorField(key="model", label="Model", placeholder="gpt-4o-mini", required=False),
        ),
    ),
    ConnectorSpec(
        id="image_api", name="Image Generation", category="AI",
        summary="Generate images via OpenAI-compatible endpoint.",
        docs_url="https://platform.openai.com/api-keys",
        fields=(
            ConnectorField(key="api_url", label="Endpoint URL", placeholder="https://api.openai.com/v1", kind="url"),
            ConnectorField(key="api_key", label="API key", placeholder="sk-...", secret=True, kind="password"),
            ConnectorField(key="model", label="Model", placeholder="dall-e-3", required=False),
        ),
    ),
)

_BY_ID = {spec.id: spec for spec in CATALOG}


def get_spec(connector_id: str) -> Optional[ConnectorSpec]:
    return _BY_ID.get(connector_id)


def spec_to_dict(spec: ConnectorSpec) -> dict:
    return {
        "id": spec.id, "name": spec.name, "category": spec.category,
        "summary": spec.summary, "docs_url": spec.docs_url, "note": spec.note,
        "fields": [
            {"key": f.key, "label": f.label, "placeholder": f.placeholder,
             "secret": f.secret, "required": f.required, "help": f.help, "kind": f.kind}
            for f in spec.fields
        ],
    }


def missing_required(spec: ConnectorSpec, values: dict) -> list[str]:
    return [f.key for f in spec.fields if f.required and not str(values.get(f.key, "") or "").strip()]
