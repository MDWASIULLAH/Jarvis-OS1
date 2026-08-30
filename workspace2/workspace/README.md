# JARVIS — Local Intelligent Agent

Built from your spec, in the order it asked for: security first, then the
interface, then memory, then capabilities. This README is organized by
**what's actually true**, not by what would be nice to say.

## JARVIS Core additions (reviewed, fixed, and tested — not just copied in)

You supplied a reference project (structured as `agents/`, `tasks/`,
`knowledge/`, `observability/`, `plugins/`, `companions/`, `core/`) that was
built to plug directly into this codebase — it imports the actual
`SemanticIndex` and `LocalEncryptor` classes from this project, not
placeholders. It was genuinely well-designed: each "agent" is a narrow
system-prompt role routed by keyword matching, not a claim of independent
tool access — the same security posture as everything else here. I reviewed
every file, then:

- **Completed `api/v1.py`**, which cut off mid-function — the OCR endpoint
  decoded an image and never called OCR or returned anything.
- **Wrote the missing `core/runtime.py`** — the composition root that
  actually wires memory, security, models, agents, tasks, audit, knowledge,
  and companions together. It was referenced everywhere but never included.
- **Found and fixed a real concurrency bug** via an actual HTTP request
  (not just unit tests in isolation): `MemorySystem`'s SQLite connections
  were created without `check_same_thread=False`, so the *first* real
  request through FastAPI's worker threadpool crashed with
  `sqlite3.ProgrammingError`. This bug existed in my own original code too
  — it just never surfaced because earlier tests only called the classes
  directly in the same thread. Fixed with `check_same_thread=False` + a
  lock, matching the pattern the reference code already used correctly.
- **Fixed a wrong relative import** (`.runtime` → `..core.runtime`) that
  broke the whole app on startup.
- Added a `ModelRouter` + `OpenAICompatibleBackend` to `llm_interface.py`
  (additive, nothing removed) — an honest version of "route between
  models": exactly one local backend and one *opt-in* cloud/LAN backend
  (works for Qwen/DeepSeek/Mistral/etc. via any OpenAI-compatible server),
  never auto-selecting a cloud call without `JARVIS_ALLOW_CLOUD=true`.

New pieces, all exercised with real HTTP requests through FastAPI's test
client (not just called directly) because that's what caught both bugs
above:

- **`app/agents/orchestrator.py`** — routes a request to 1–4 specialist
  system-prompt "agents" (coding/research/memory/planning/etc.), pulls
  relevant semantic-memory context in, and returns per-agent text results.
  Never executes real actions itself — same SecurityGate as always.
- **`app/tasks/store.py`** — a real SQLite task queue (queued → running →
  completed/failed) that survives a restart.
- **`app/knowledge/knowledge_base.py`** — real RAG: chunks text, indexes it
  with TF-IDF, encrypts chunks at rest, supports delete-with-confirmation.
- **`app/observability/audit.py`** — an audit trail that redacts obvious
  secret-shaped fields (`*_key`, `*_token`, `password`) before writing.
- **`app/observability/system_monitor.py`** — real CPU/RAM/disk numbers via
  `psutil` (optional dependency; degrades gracefully without it).
- **`app/companions/companions.py`** — the pairing-code → bearer-token
  protocol a *future* native mobile/desktop companion app would use to talk
  to this backend. This is the backend half only — there's no app yet.
- **`app/plugins/registry.py`** — a manifest of known integrations
  (GitHub, Slack, Notion, Google Calendar, etc.), each disabled by default
  and flagged as needing real OAuth. Listing a plugin here is not the same
  as it being wired to a working connection.
- **`app/api/v1.py`** — versioned surface (`/v1/...`) for all of the above.
  `api/routes.py` (the original surface) is untouched and still works.

## Frontend integration (your uploaded UI design, wired to the real backend)

You supplied a separate, complete vanilla-JS/HTML/CSS frontend (3D orbital
visualization, camera, voice, chat history, themes, slash commands) built to
call a raw OpenAI-compatible endpoint with a client-side stored API key.
It's genuinely well-built — I kept essentially all of it. What changed:

- **`js/api.js`** — rewritten so `sendMessage()` calls this project's real
  `/v1/chat` instead of a third-party endpoint. The public interface
  (`init`/`sendMessage`/`setConfig`/`getConfig`) is identical, so
  `chat.js`, `camera.js`, `upload.js`, `voice.js`, `history.js` needed *zero*
  changes — they already only talked to `api.js`, never to a remote host
  directly.
- **Attachments now do something real**: an uploaded photo goes through this
  project's tested OCR before the model ever sees it; a PDF/DOCX goes
  through the tested document reader. Neither is a simulated description.
- **`js/settings.js`** — API key + OpenAI-endpoint fields replaced with
  backend URL + local/cloud provider + a live "Test Connection" check.
- **Added `/v1/search`** (real, DuckDuckGo Instant Answer, keyless — limited
  to direct factual questions, not general search) and **CORS** on the
  FastAPI app, since a statically-served frontend is a different origin
  from the browser's point of view.
- The offline pattern-matching fallback is untouched in spirit — still
  answers jokes/time/poems/etc. when the backend isn't running — just
  relabeled from "no API key" to "backend not reachable," since that's the
  actual condition now.

`frontend-ui/` is the result — see SETUP.md to run it against the backend.

## Tested and real (75/75 passing)

- **`app/security/permissions.py`** — hard blocks on financial/payment apps
  and background monitoring; confirmation required for email send, file
  delete, shutdown, calendar add, clipboard access.
- **`app/memory/memory_store.py`** — three-tier memory: short-term session
  context, AES-256-GCM-encrypted long-term facts in SQLite, predictive
  action logging by hour/weekday.
- **`app/memory/semantic_search.py`** — TF-IDF semantic-ish search over
  long-term facts. No model download needed, so it works fully offline;
  swap in real sentence embeddings later without changing the interface.
- **`app/brain/llm_interface.py`** — pluggable local LLM (Ollama by
  default, mock fallback for testing).
- **`app/capabilities/email_module.py`** — draft → preview → approve → send.
- **`app/capabilities/weather_module.py`** — Open-Meteo, no key.
- **`app/capabilities/news_module.py`** — Google News RSS, no key; NewsAPI
  if you add a key.
- **`app/capabilities/location_services.py`** — geocoding (Nominatim),
  routing (OSRM), IP lookup (ip-api.com), all keyless.
- **`app/capabilities/knowledge_apis.py`** — dictionary, DuckDuckGo instant
  answers, Stack Exchange search, all keyless.
- **`app/capabilities/fun_and_space.py`** — NASA picture of the day, space
  news, Hacker News, QR codes, all keyless.
- **`app/capabilities/translate_currency.py`** — LibreTranslate + currency,
  both honest about free-tier terms that have changed before.
- **`app/capabilities/document_reader.py`** + **`document_writer.py`** —
  real PDF/DOCX reading, real DOCX/PPTX/XLSX generation. Round-trip tested:
  write a file, read it back, confirm the content matches.
- **`app/capabilities/vision_ocr.py`** — real OCR via Tesseract. Tested by
  generating an image with text and reading it back correctly.
- **`app/capabilities/code_executor.py`** — sandboxed-ish Python execution
  with a timeout. Tested including the timeout path (an infinite loop
  actually gets killed).
- **`app/capabilities/github_client.py`** — real GitHub REST API client.
  I ran this live against the real API while building it (see below) —
  it correctly hit GitHub's rate limit and failed soft instead of crashing,
  which is exactly the behavior it's supposed to have.
- **`app/api/routes.py`** + **`app/main.py`** — FastAPI server. (The newest
  modules above aren't wired into routes yet — same import-and-call pattern
  as everything else there; happy to wire them in if useful.)

## Written correctly, but *you* have to verify these — not me

These need your own credentials or your own device, and I have no way to
test them from this sandbox. I'm telling you this directly instead of
claiming a false "5/5" — the code follows each platform's real, documented
API, but "compiles and looks right" isn't the same as "verified working,"
and only you can close that gap:

- **`app/capabilities/youtube_client.py`** — needs a free Google Cloud API
  key. googleapis.com isn't reachable from this sandbox.
- **`app/capabilities/chat_platforms.py`** — Telegram + Discord bots, both
  free to create, no business verification. api.telegram.org / discord.com
  aren't reachable from this sandbox. **WhatsApp is deliberately excluded**:
  the official API needs Meta business verification, and the unofficial
  routes violate WhatsApp's Terms of Service and risk your account getting
  banned — Telegram/Discord get you the same result without that risk.
- **`app/capabilities/smart_home.py`** — needs a running Home Assistant
  instance + token.
- **`app/capabilities/voice_pipeline.py`** — real faster-whisper (STT) and
  Piper (TTS) integration code. This sandbox has no microphone or speaker
  at all — there is nothing for me to test this against, ever, from here.
- **`app/capabilities/desktop_automation.py`** — real pyautogui integration
  for opening apps / clicking / typing / screenshots, gated through the
  security layer. This sandbox has no display (headless container) — same
  situation as voice: nothing to verify against from this side.

## What I'm not going to pretend to build

**Mobile app control** (tapping/reading other apps on your phone) can't be
done with more Python backend code, full stop. It needs a *separate* native
Android app using the Accessibility Service API — real app development,
real Google Play policy review, months of dedicated work — and iOS doesn't
practically allow this kind of third-party automation at all. This isn't a
corner being cut; it's a genuinely different project than the one we've
been building.

**Wake-word detection and live camera vision** hit the same wall as voice
and desktop automation above: they need to run continuously against real
hardware (mic / camera) that only exists on your device, not in a chat
conversation. I can point you at the standard tools (openWakeWord or
Porcupine for wake-word; a vision model over camera frames for live vision)
if/when you're ready to wire them up on your machine.

**Multi-agent orchestration** is an architecture decision, not a checkbox —
happy to design that properly as its own phase, rather than bolt it on
here.

## On the "5 stars everywhere" ask

I can't honestly rate Desktop control, Mobile control, or live Voice as
5/5 today, and saying so wouldn't become true no matter how much more code
gets written in this chat. Coding assistant, Memory, and Vision (OCR) all
made real, tested progress this round. Desktop control and Voice have real,
correct reference code now, waiting on your hardware to actually prove out.
Mobile control needs a different project entirely, as above.

## Production frontend

`frontend-v2/` is the official frontend. Run `npm install` and `npm run build` in that directory; FastAPI serves the exported `frontend-v2/out/` application at `/`. The prior prototype is retained only at `legacy/frontend-ui/`.

## Setup

See `SETUP.md`.
