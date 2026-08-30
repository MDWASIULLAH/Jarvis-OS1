# Running JARVIS locally

## 1. Backend

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q            # should show 75 passed
uvicorn app.main:app --reload --port 8000
```

## 2. Connect a local LLM (optional but recommended)

Install [Ollama](https://ollama.com), then:

```bash
ollama pull llama3.1:8b
ollama serve
```

`llm_interface.py` auto-detects Ollama on `localhost:11434` at startup and
falls back to a mock responder if it's not running — so the server always
comes up cleanly either way.

To use a cloud or LAN model instead (Qwen/DeepSeek/Mistral/etc. via any
OpenAI-compatible server, or a real hosted API), set before starting uvicorn:

```bash
export JARVIS_ALLOW_CLOUD=true
export JARVIS_CLOUD_BASE_URL=http://localhost:8080/v1   # or a real endpoint
export JARVIS_CLOUD_MODEL=your-model-name
export JARVIS_CLOUD_API_KEY=...                         # if the endpoint needs one
```

Requests still default to "local" — cloud only answers when a client
explicitly asks for `provider: "cloud"` *and* this is set.

## 3. Frontend — two options, for different purposes

**`frontend/jarvis-chat-demo.jsx`** — the live Claude.ai artifact demo. Calls
Claude directly from the browser (real vision, web search, file
understanding). Does not talk to your Python backend at all — a UI/concept
preview you can try immediately with nothing running locally.

**`frontend-ui/`** — a full standalone JARVIS UI (3D visualization, camera,
voice, chat history, themes, slash commands) wired to your *real* local
backend over HTTP:

```bash
# Terminal 1 -- backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 -- frontend (any static file server works)
cd frontend-ui
python -m http.server 5500
```

Open `http://localhost:5500`. Settings → AI Model lets you change the
backend URL (defaults to `http://localhost:8000`) and switch between
"local" and "cloud". If the backend isn't reachable, the UI falls back to
offline pattern responses instead of erroring out — attach a photo or PDF
once it *is* reachable and the backend will actually OCR/read it before
replying, not just acknowledge that a file exists.

## 4. Try the safety gate directly

```bash
curl -X POST localhost:8000/email/draft \
  -H "Content-Type: application/json" \
  -d '{"to": "boss@example.com", "intent": "requesting leave tomorrow"}'
```

Confirm-and-send flows follow the same `request_*` → `confirmation_id` →
`execute_*` pattern used throughout — see `/v1/actions/confirm` for the
newer versioned equivalent (memory/knowledge deletion currently route
through it).

## 5. Explore the new v1 API

```bash
curl localhost:8000/v1/status
curl -X POST localhost:8000/v1/agents/tasks -H "Content-Type: application/json" \
  -d '{"text": "help me debug a failing test"}'
curl "localhost:8000/v1/knowledge/search?query=your+topic"
curl localhost:8000/v1/system/status
```

## 6. Next steps

Pick a module from README.md's "written correctly, you verify" or "not
going to pretend to build" lists, or ask Claude to keep building it out.
For anything touching audio hardware, a real display, or a real OS, this is
a good project to continue in **Claude Code**, running directly on your own
machine.
