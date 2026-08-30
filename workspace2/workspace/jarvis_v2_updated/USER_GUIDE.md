# JARVIS AI Operating System v2 - USER GUIDE

## Overview

JARVIS (Just A Rather Very Intelligent System) is a local-first AI assistant that runs on your machine. It combines a trained intent classifier, real tool execution, and an optional local language model to answer questions and perform actions.

## Quick Start

### Prerequisites
- Python 3.9+
- Optional: Ollama for local LLM (install from https://ollama.com/)

### Installation

```bash
# Clone the repository or extract the ZIP
cd jarvis/backend

# Install Python dependencies
pip install -r requirements.txt

# Install tesseract-ocr for image text extraction (optional)
# Linux: apt install tesseract-ocr
# macOS: brew install tesseract

# If you want voice features, optionally install
pip install faster-whisper
pip install pyautogui
```

### Starting the Server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### Running with Ollama (recommended)

```bash
# Install Ollama and pull a model first
ollama pull llama3.1:8b

# Start JARVIS (default uses localhost:11434)
uvicorn app.main:app --reload
```

## Architecture

```
User Input -> Intent Classifier (NLU) -> Decision Engine -> Tool Execution
                                                              |
                                                              v
User Output <- Reflection Engine <- Response Composer <- Tool Results
```

### Core Components

| Component | Purpose |
|-----------|---------|
| **Brain Core** | Main pipeline: understand -> plan -> act -> reflect -> respond |
| **Decision Engine** | Determines which model, tools, and connectors to use |
| **Reflection Engine** | Evaluates task success and suggests improvements |
| **Goal Manager** | Manages long-term goals, milestones, and task tracking |
| **Memory System** | 5-tier: short-term, long-term (encrypted), predictive, preferences, summaries |
| **Security Gate** | Blocks financial transactions, requires confirmation for sensitive actions |

## Features

### Natural Language Commands

Type or speak to JARVIS. It understands:
- Factual queries: "What is quantum computing?"
- Math: "Calculate 15% of 85"
- Time: "What time is it in Tokyo?"
- Weather: "Weather in London"
- News: "News about AI"
- Translation: "Translate 'hello' into Spanish"
- Currency: "Convert 100 USD to EUR"
- Image search: "Show me pictures of Saturn"
- Image generation: "Generate an image of a cyberpunk city"
- Web browsing: "Read https://example.com"
- Memory: "Remember my train leaves at 7:40"

### Voice Commands

Say "Jarvis" followed by your command:
- "Jarvis, be silent" - Disables speech
- "Jarvis, speak" - Enables speech
- "Jarvis, change your voice" - Cycles voice profiles
- "Jarvis, use a male voice" - Switches to male voice
- "Jarvis, use a female voice" - Switches to female voice
- "Jarvis, settings" - Opens settings panel
- "Jarvis, fullscreen" - Enters fullscreen mode
- "Jarvis, theme change" - Cycles themes

## Connectors

### Available Connectors (38 total)

**Email**: Gmail, Outlook
**Productivity**: Google Drive, Google Calendar, Google Docs, Notion
**Developer**: GitHub, GitLab, Docker, Supabase, Firebase, Vercel, Cloudflare
**Messaging**: Slack, Discord, Telegram, WhatsApp Business
**Project Management**: Jira, Linear, Trello
**Media**: YouTube, Spotify
**Cloud/AI**: OpenAI, Anthropic, Gemini, OpenRouter, Ollama, HuggingFace
**Cloud**: AWS, Azure
**Storage**: Dropbox, OneDrive
**Data**: OpenWeatherMap, NewsAPI, Google Maps
**Design**: Figma, Canva
**Smart Home**: Home Assistant
**Social**: LinkedIn, Reddit

### Connecting a Service

1. Click the **+** button in the chat input bar
2. Select **Connectors**
3. Find the service you want to connect
4. Enter required credentials (API keys, tokens, etc.)
5. Click **Test** to verify the connection
6. Once verified, the connector is active

### Gmail Setup Example

1. Enable 2-step verification on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. In JARVIS Connectors, enter your Gmail address and the 16-character App Password
4. Test the connection

### Telegram Bot Setup

1. Message @BotFather on Telegram to create a new bot
2. Copy the bot token
3. In JARVIS Connectors, enter the bot token
4. Start chatting with your bot on Telegram for remote control

### WhatsApp Business Setup

WhatsApp requires Meta Business verification:
1. Create a Meta Business account at https://business.facebook.com
2. Register a WhatsApp Business API phone number
3. Get your phone number ID and access token
4. Enter credentials in JARVIS Connectors

For personal notifications without business verification, use Telegram or Discord instead.

## Goal Manager

### Creating Goals

From the API or programmatically:

```json
POST /v1/goals
{
  "title": "Complete project documentation",
  "description": "Write all API docs and user guide",
  "scope": "project",
  "priority": "high",
  "target_date": "2026-08-15"
}
```

### Goal Scopes
- **daily**: Tasks to complete today
- **weekly**: Objectives for the week
- **project**: Medium-term project goals
- **long_term**: Strategic objectives

### Tracking Progress

- Add milestones to break goals into checkpoints
- Add dependencies to link related goals
- Progress is automatically calculated from completed tasks and milestones
- Use `/v1/goals/daily` for daily planning suggestions

## Telegram Remote Control

Connect a Telegram bot to control JARVIS remotely. Supported commands:

| Command | Description |
|---------|-------------|
| /status | System status (CPU, RAM, disk) |
| /screenshot | Take and send a screenshot |
| /open [app] | Open an application |
| /cpu | CPU usage percentage |
| /ram | RAM usage |
| /disk | Disk usage |
| /clipboard | Read clipboard content |
| /search [pattern] | Search files in home directory |
| /files [path] | List directory contents |
| /mkdir [path] | Create a directory |
| /move [src] [dst] | Move a file |
| /rename [old] [new] | Rename a file |
| /compress [folder] | Create and send a ZIP |
| /download [path] | Download a file |
| /logs | Send audit logs |
| /weather [city] | Get weather for a city |
| /news | Get news headlines |
| /remember [fact] | Store a fact in memory |
| /recall [query] | Search stored memories |

### Authentication

Set authorized user IDs in the TelegramClient to restrict access:
```python
telegram.set_auth_users({123456789, 987654321})
```

## Desktop Automation

JARVIS can interact with your desktop (requires confirmation):
- Open applications: "Open Chrome"
- Open URLs: "Open https://github.com"
- Take screenshots: "Take a screenshot"
- System monitoring: "What's my CPU usage?"
- File operations: create, rename, move, search

For full desktop automation (mouse/keyboard), install pyautogui:
```bash
pip install pyautogui
```

## Settings Panel

Access via the J.A.R.V.I.S header or Ctrl+, keyboard shortcut:

### AI Model
- Backend URL (default: http://localhost:8000)
- Provider (local/cloud)
- Test connection

### Voice
- Voice profiles: Tony Stark, Male, Female, Calm, Friendly, Professional
- Rate, pitch, volume sliders
- Voice test button

### Microphone
- Wake word toggle
- Always listening toggle
- Continuous listening toggle

### Speech Mode
- Speak/Silent toggle: controls whether JARVIS speaks responses aloud

### Visual
- 3D Background toggle: show/hide the orbital visualization
- Theme switcher: Default, Midnight Blue, Cyber Neon, Crimson Red, Light Mode
- Performance mode: reduce visual effects
- Animation quality and FPS controls

### Developer
- Developer mode: shows raw API responses and debug info

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Ctrl+N | New chat |
| Ctrl+, | Settings |
| Escape | Close modal/sheet |
| ? | Show shortcuts |
| /help | Show commands |
| /theme | Cycle themes |
| /calc | Calculator |
| /status | System info |
| Ctrl+V | Paste image |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| JARVIS_DATA_DIR | ~/.jarvis | Data directory |
| JARVIS_OLLAMA_HOST | http://localhost:11434 | Ollama host |
| JARVIS_OLLAMA_MODEL | llama3.1:8b | Default LLM model |
| JARVIS_CLOUD_BASE_URL | (none) | Cloud LLM endpoint |
| JARVIS_CLOUD_API_KEY | (none) | Cloud API key |
| JARVIS_CLOUD_MODEL | (none) | Cloud model name |
| JARVIS_ALLOW_CLOUD | false | Enable cloud model |
| JARVIS_IMAGE_API_URL | (none) | Image generation endpoint |
| JARVIS_IMAGE_API_KEY | (none) | Image generation API key |
| JARVIS_IMAGE_MODEL | (none) | Image generation model |

## Privacy & Security

- **Local-first**: All processing happens on your machine by default
- **Encrypted storage**: AES-256-GCM encryption for memory and connector credentials
- **No telemetry**: JARVIS does not phone home or collect usage data
- **Confirmation gates**: Sensitive actions (email send, file delete, app open) require explicit approval
- **Financial safety**: All financial/payment app interactions are hard-blocked
- **Audit trail**: All actions are logged with secret fields redacted

## Troubleshooting

### "No backend connection"
- Ensure the FastAPI server is running: `uvicorn app.main:app --reload`
- Check your network/firewall allows port 8000
- Try the "Test Connection" button in Settings

### "JARVIS answers with fallback responses"
- Install Ollama and pull a model for better responses
- Without Ollama, JARVIS uses its built-in local reasoning engine

### "Voice recognition not working"
- Use Chrome or Edge for best SpeechRecognition API support
- Grant microphone permissions when prompted
- Voice recognition requires internet for the Web Speech API

### "Connector test fails"
- Double-check your API key/token for typos
- Ensure the required API is enabled in the provider's console
- Some keys (OpenWeatherMap) can take hours to activate
