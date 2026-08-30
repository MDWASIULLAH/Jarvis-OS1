# JARVIS AI Operating System v2 - CHANGELOG

## 2026-07-29: Production-Ready AI Operating System Update

### New Modules

#### Decision Engine (`app/brain/decision_engine.py`)
- Deterministic routing engine that sits between intent classification and tool execution
- Decides which model (local_llm, cloud_llm, local_reasoning, none), tool, connector, and API to use
- Stores decision history for audit and improvement
- Pattern-matching override for code, email, calendar, automation, and URL detection
- 25 intent-to-decision mappings covering all supported intents

#### Goal Manager (`app/goals/manager.py`)
- Full goal lifecycle management (create, update, delete, track progress)
- Support for scopes: daily, weekly, project, long_term
- Task hierarchy: parent/child goals, dependencies, milestones
- Progress tracking with automatic recalculation
- Status tracking: pending, in_progress, completed, cancelled, blocked
- Auto-plan daily suggestions based on active goal priorities
- Due date reminder system
- SQLite-backed persistent storage

#### WhatsApp Business Integration (`app/capabilities/chat_platforms.py`)
- Official WhatsApp Cloud API (Business) client
- Send text messages, images, and documents
- Clear documentation of Meta Business verification requirements
- Honest warning about unofficial WhatsApp Web automation risks

### Enhanced Modules

#### Telegram Remote Control (`app/capabilities/chat_platforms.py`)
- 20+ slash commands: /start, /help, /status, /screenshot, /open, /cpu, /ram, /disk
- File operations via Telegram: /search, /files, /mkdir, /move, /rename, /compress, /download
- Memory operations: /remember, /recall
- Weather and news queries: /weather, /news
- Screenshot capture and photo return
- File/document sending (ZIP, logs, database)
- Role-based authentication with authorized user IDs
- System commands: /shutdown, /restart, /lock, /clipboard

#### Reflection Engine (`app/brain/cognition.py`)
- Enhanced post-task evaluation: success/failure tracking
- Improvement suggestions when tools fail
- Reflection history storage (100 entries)
- Integration with Decision Engine for memory logging
- Success tracking in reflection entries

#### Connectors (`app/connectors/`)
- **New verifiers**: GitLab, Notion, Jira, Trello, Spotify, Dropbox, Figma
- **New connectors**: Outlook, WhatsApp Business, Google Maps, Canva
- Total connectors: 38 (up from 33)
- Total verifiers: 18 (up from 11)

#### Memory System (`app/memory/memory_store.py`)
- **New Tier 4**: PreferenceMemory - stores user voice, theme, and behavior preferences
- **New Tier 5**: ConversationSummaries - auto-generates summaries from chat turns
- Auto-summarization of every conversation turn
- Preference persistence (get, set, delete by key/category)

#### API (`app/api/v1.py`)
- **Goal endpoints**: POST/GET/PUT/DELETE /goals, /goals/summary, /goals/daily, /goals/reminders
- **Goal task/dependency/milestone endpoints**: POST /goals/{id}/tasks, /dependencies, /milestones
- **Decision Engine endpoints**: GET /decision/history
- **Reflection endpoints**: GET /reflection/history
- **Memory preferences**: POST/GET/DELETE /memory/preferences
- **Memory summaries**: GET /memory/summaries, /memory/summaries/search
- New Pydantic models: GoalCreateRequest, GoalUpdateRequest, MilestoneRequest

### Enhanced Frontend

#### Voice Commands (`frontend-ui/js/speech.js`)
- "Jarvis, be silent" - disables speech
- "Jarvis, speak" - enables speech
- "Jarvis, use a male voice" - switches to male profile
- "Jarvis, use a female voice" - switches to female profile
- "Jarvis, change your voice" - cycles through voice profiles

#### Settings Panel (`frontend-ui/js/settings.js`)
- **Speak/Silent toggle**: Enable or disable text-to-speech output
- **3D Background toggle**: Show or hide the orbital visualization canvas
- **Theme switcher**: Default, Midnight Blue, Cyber Neon Green, Crimson Red, Light Mode
- **Performance mode**: Reduce visual effects for smoother performance
- **Developer mode**: Show raw API responses and debug indicator

### Bug Fixes
- Fixed `neural_system` typo in Decision Engine (was causing import errors)
- Fixed summary ID collision in conversation summaries (UUID-based now)

### Backward Compatibility
- All existing APIs unchanged
- All existing frontend features preserved
- All existing configuration and data formats maintained
- Existing connector credentials continue to work
