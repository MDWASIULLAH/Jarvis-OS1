"""
api/v1.py

Versioned API for JARVIS Core additions.

Legacy routes remain in ``api/routes.py`` unchanged. New clients should use
this explicit versioned surface so future evolution stays non-breaking.
"""

from __future__ import annotations

import base64
import binascii
import os
import json
import tempfile
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..capabilities import app_launcher, web_research
from ..capabilities.document_reader import read_document
from ..capabilities.knowledge_apis import quick_answer, _clean_query
from ..capabilities.vision_ocr import extract_text_from_image, ocr_available
from ..goals.manager import GoalScope, GoalStatus, GoalPriority
from ..security.permissions import ActionType
from ..connectors.registry import CATALOG, get_spec
from ..connectors.verify import verify as verify_connector
from ..core.runtime import runtime

router = APIRouter(prefix="/v1", tags=["JARVIS Core"])


class ChatAttachment(BaseModel):
    name: str = Field(max_length=300)
    media_type: str = Field(max_length=100)
    base64: str = Field(max_length=15_000_000)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    system: Optional[str] = Field(default=None, max_length=5000)
    # "auto" is the default: the brain picks the engine per request from the
    # intent it classified, instead of pinning every turn to one dropdown value.
    provider: str = Field(default="auto", pattern="^(local|cloud|auto)$")
    attachments: list = Field(default_factory=list)


class AgentTaskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    provider: str = Field(default="auto", pattern="^(local|cloud|auto)$")


class MemoryFactRequest(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="general", max_length=100)


class KnowledgeIngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=100000)
    source: str = Field(default="manual", max_length=500)
    metadata: dict = Field(default_factory=dict)


class ConfirmRequest(BaseModel):
    confirmation_id: str


class PairRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)
    label: str = Field(default="Unnamed device", max_length=200)
    platform: str = Field(min_length=2, max_length=30)
    capabilities: list = Field(default_factory=list)


class CompanionEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


class PluginEnableRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=100)


class OCRRequest(BaseModel):
    image_base64: str = Field(min_length=10, max_length=12_000_000)


class ConnectorSaveRequest(BaseModel):
    values: dict = Field(default_factory=dict)


class ConnectorTestRequest(BaseModel):
    values: dict = Field(default_factory=dict)


class ToolToggleRequest(BaseModel):
    tool_id: str = Field(min_length=1, max_length=100)
    enabled: bool = True


class GoalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    scope: str = Field(default="project", pattern="^(daily|weekly|project|long_term)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    parent_id: Optional[str] = None
    target_date: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class GoalUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    scope: Optional[str] = Field(default=None, pattern="^(daily|weekly|project|long_term)$")
    status: Optional[str] = Field(default=None, pattern="^(pending|in_progress|completed|cancelled|blocked)$")
    priority: Optional[str] = Field(default=None, pattern="^(low|medium|high|critical)$")
    parent_id: Optional[str] = None
    target_date: Optional[str] = None
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Optional[dict] = None


class MilestoneRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    target_date: Optional[str] = None


def _extract_attachment_text(attachment: dict) -> str:
    """Turns an uploaded image/PDF/DOCX into real extracted text via the
    existing, tested capabilities -- not a description of a photo's scene
    (that needs a vision-capable local model), but real text pulled from it."""
    name = attachment.get("name", "attachment")
    media_type = attachment.get("media_type", "")
    try:
        raw = base64.b64decode(attachment.get("base64", ""), validate=False)
    except (binascii.Error, ValueError):
        return f"[{name}: could not decode attachment]"

    suffix = ".bin"
    if media_type.startswith("image/") or name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        suffix = ".png"
    elif media_type == "application/pdf" or name.lower().endswith(".pdf"):
        suffix = ".pdf"
    elif name.lower().endswith(".docx"):
        suffix = ".docx"

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        if suffix == ".png":
            text = extract_text_from_image(tmp_path)
            return f"[Image '{name}', OCR text follows]\n{text or '(no readable text found in the image)'}"
        text = read_document(tmp_path)
        return f"[Document '{name}', extracted text follows]\n{text or '(no extractable text found)'}"
    except Exception as exc:  # noqa: BLE001 -- always degrade to a note, never 500 the whole chat turn
        return f"[{name}: couldn't process this attachment ({exc})]"
    finally:
        os.unlink(tmp_path)


def _decision_payload(decision: Any) -> dict:
    return {
        "allowed": decision.allowed,
        "requires_confirmation": decision.requires_confirmation,
        "reason": decision.reason,
        "confirmation_id": decision.confirmation_id,
    }


def _require_device(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A companion bearer token is required.")
    device = runtime.companions.authenticate(authorization.split(" ", 1)[1].strip())
    if not device:
        raise HTTPException(status_code=401, detail="Invalid or revoked companion token.")
    return device


@router.get("/status")
def status():
    return {
        "name": "JARVIS Core",
        "time": datetime.now().astimezone().isoformat(),
        "model": runtime.models.status(),
        "features": {
            "multi_agent": True,
            "local_knowledge": True,
            "device_companion_protocol": True,
            "encrypted_memory": True,
            "streaming": True,
            # Probed, not hardcoded: OCR needs the native tesseract binary. The
            # UI uses this to explain the gap before the user uploads a file and
            # gets an error, which is the only way to find out otherwise.
            "ocr": ocr_available(),
        },
    }


@router.post("/chat")
def chat(request: ChatRequest):
    """Every turn now goes through the Brain Core.

    The old version forwarded raw text straight to the model, which is why a
    machine without a local model answered "[mock response] ...", and why
    "open Chrome" or "show me a picture of Saturn" produced prose instead of
    an action. The brain classifies the request, calls real tools, and returns
    the trace of what actually ran alongside the reply.
    """

    attachment_text = ""
    if request.attachments:
        attachment_text = "\n\n".join(_extract_attachment_text(a) for a in request.attachments[:5])

    runtime.memory.short_term.add("user", request.text)
    thought = runtime.brain.think(request.text, provider=request.provider, attachment_text=attachment_text)
    runtime.memory.short_term.add("jarvis", thought.reply)
    runtime.memory.predictive.log_action(f"chat:{thought.intent}")
    runtime.memory.summaries.record(
        session_id=str(uuid.uuid4()),
        user_text=request.text[:2000],
        jarvis_reply=thought.reply[:4000],
        intent=thought.intent,
        summary=f"{thought.intent}: {thought.reply[:200]}",
        tools_used=[c.name for c in thought.tools if c.ok],
    )
    runtime.audit.record(
        "chat",
        "completed",
        {
            "provider": request.provider,
            "intent": thought.intent,
            "tools": [c.name for c in thought.tools if c.ok],
            "attachments": len(request.attachments),
        },
    )
    payload = thought.to_dict()
    resolved = str(thought.route.get("provider", request.provider))
    payload["provider"] = resolved
    payload["requested_provider"] = request.provider
    payload["privacy"] = "local" if resolved == "local" else "cloud-opt-in"
    return payload


@router.get("/brain/status")
def brain_status():
    return runtime.brain.status()


@router.post("/brain/reload-model")
def reload_intent_model():
    """Re-reads the trained intent model from disk after `train_intents.py` runs."""
    runtime.brain.intents = runtime.brain.intents.__class__()
    return runtime.brain.intents.status()


@router.get("/search")
def search(query: str):
    """Cleaned query search via DuckDuckGo Instant Answer API."""
    clean = _clean_query(query)
    answer = quick_answer(clean)
    runtime.audit.record("search", "completed", {"query_len": len(query)})
    return {"answer": answer, "engine": "duckduckgo_instant_answer", "query": clean}


@router.post("/chat/stream")
def stream_chat(request: ChatRequest):
    def events():
        """Streams the brain's actual work: intent, plan, tool results, reply.

        Tools have to finish before the words exist (an image search cannot be
        streamed token by token), so the stream reports progress events first
        and then streams the composed reply.
        """

        runtime.memory.short_term.add("user", request.text)
        try:
            attachment_text = ""
            if request.attachments:
                attachment_text = "\n\n".join(_extract_attachment_text(a) for a in request.attachments[:5])

            thought = runtime.brain.think(request.text, provider=request.provider, attachment_text=attachment_text)
            yield f"event: intent\ndata: {json.dumps({'intent': thought.intent, 'confidence': round(thought.confidence, 3), 'plan': thought.plan}, ensure_ascii=False)}\n\n"
            # Which engine the brain picked for this request, and whether it was
            # actually used. The UI prints a model name beside every answer; it
            # should be the engine that ran, not the last value of a dropdown.
            yield f"event: route\ndata: {json.dumps(thought.route, ensure_ascii=False)}\n\n"
            for call in thought.tools:
                yield f"event: tool\ndata: {json.dumps(call.to_dict(), ensure_ascii=False)}\n\n"
            # Media exists before the words do (an image cannot be streamed a
            # token at a time), so it is announced here. Without this frame the
            # streaming path dropped every generated image and only the caption
            # reached the browser.
            if thought.media:
                yield f"event: media\ndata: {json.dumps({'items': thought.media}, ensure_ascii=False)}\n\n"
            if thought.sources:
                yield f"event: sources\ndata: {json.dumps({'items': thought.sources}, ensure_ascii=False)}\n\n"
            if thought.confirmation:
                yield f"event: confirmation\ndata: {json.dumps(thought.confirmation, ensure_ascii=False)}\n\n"

            words = thought.reply.split(" ")
            for start in range(0, len(words), 5):
                chunk = " ".join(words[start:start + 5])
                if start + 5 < len(words):
                    chunk += " "
                yield f"event: delta\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

            runtime.memory.short_term.add("jarvis", thought.reply)
            runtime.memory.predictive.log_action(f"chat:{thought.intent}")
            runtime.audit.record("chat_stream", "completed", {"provider": thought.route.get("provider", request.provider), "intent": thought.intent})
            yield f"event: done\ndata: {json.dumps(thought.to_dict(), ensure_ascii=False)}\n\n"
        except Exception as exc:
            runtime.audit.record("chat_stream", "failed", {"error": str(exc)})
            yield f"event: error\ndata: {json.dumps({'message': f'The turn failed: {exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # Without the buffering hint a proxy can hold the whole response back,
        # which turns the stream into one late blob.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/agents/plan")
def agent_plan(text: str):
    return runtime.agents.plan(text)


@router.post("/agents/tasks")
def execute_agent_task(request: AgentTaskRequest):
    return runtime.agents.execute(request.text, request.provider)


@router.get("/agents/tasks")
def list_agent_tasks(limit: int = 50):
    return {"tasks": runtime.tasks.list(limit)}


@router.get("/agents/tasks/{task_id}")
def get_agent_task(task_id: str):
    task = runtime.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@router.get("/memory/facts")
def list_memory_facts(category: Optional[str] = None):
    return {"facts": runtime.memory.long_term.all_facts(category)}


@router.post("/memory/facts")
def remember_fact(request: MemoryFactRequest):
    runtime.memory.long_term.remember(request.key, request.value, request.category)
    runtime.audit.record("memory", "remembered", {"key": request.key, "category": request.category})
    return {"stored": True, "key": request.key, "category": request.category}


@router.get("/memory/search")
def search_memory(query: str, top_k: int = 5):
    from ..memory.semantic_search import SemanticIndex

    index = SemanticIndex()
    index.build(runtime.memory.long_term.all_facts())
    return {"results": index.search(query, top_k=max(1, min(top_k, 20)))}


@router.delete("/memory/facts/{key}")
def delete_memory_fact(key: str):
    decision = runtime.security.check_action(
        ActionType.FILE_DELETE, target=f"memory:{key}", payload={"operation": "delete_memory", "key": key}
    )
    runtime.audit.record("memory_delete", "confirmation_requested", {"key": key})
    return _decision_payload(decision)


@router.get("/memory/insights")
def memory_insights():
    now = datetime.now()
    return {"hour": now.hour, "suggested_routines": runtime.memory.predictive.routine_for_hour(now.hour, now.weekday())}


@router.post("/memory/preferences")
def set_preference(key: str, value: str, category: str = "general"):
    runtime.memory.preferences.set(key, value, category)
    runtime.audit.record("preference", "set", {"key": key, "category": category})
    return {"stored": True, "key": key, "category": category}


@router.get("/memory/preferences")
def get_preferences(category: Optional[str] = None):
    return {"preferences": runtime.memory.preferences.get_all(category)}


@router.delete("/memory/preferences/{key}")
def delete_preference(key: str):
    runtime.memory.preferences.delete(key)
    return {"deleted": True, "key": key}


@router.get("/memory/summaries")
def list_summaries(limit: int = 20):
    return {"summaries": runtime.memory.summaries.recent(limit), "total": runtime.memory.summaries.count()}


@router.get("/memory/summaries/search")
def search_summaries(query: str, limit: int = 10):
    return {"results": runtime.memory.summaries.search(query, limit)}


@router.post("/knowledge/documents")
def ingest_knowledge(request: KnowledgeIngestRequest):
    document = runtime.knowledge.ingest_text(request.title, request.text, request.source, request.metadata)
    runtime.audit.record("knowledge", "ingested", {"document_id": document["document_id"], "source": request.source})
    return document


@router.get("/knowledge/documents")
def list_knowledge_documents():
    return {"documents": runtime.knowledge.documents()}


@router.get("/knowledge/search")
def search_knowledge(query: str, top_k: int = 5):
    return {"results": runtime.knowledge.search(query, top_k)}


@router.delete("/knowledge/documents/{document_id}")
def request_knowledge_delete(document_id: str):
    decision = runtime.security.check_action(
        ActionType.FILE_DELETE,
        target=f"knowledge:{document_id}",
        payload={"operation": "delete_knowledge", "document_id": document_id},
    )
    runtime.audit.record("knowledge_delete", "confirmation_requested", {"document_id": document_id})
    return _decision_payload(decision)


@router.post("/actions/confirm")
def confirm_action(request: ConfirmRequest):
    pending = runtime.security.confirm(request.confirmation_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Confirmation is invalid, expired, or already used.")
    if pending.action_type == ActionType.FILE_DELETE and pending.payload.get("operation") == "delete_knowledge":
        deleted = runtime.knowledge.delete_document(pending.payload["document_id"])
        runtime.audit.record("knowledge_delete", "completed", {"document_id": pending.payload["document_id"], "deleted": deleted})
        return {"completed": True, "deleted": deleted}
    if pending.action_type == ActionType.FILE_DELETE and pending.payload.get("operation") == "delete_memory":
        deleted = runtime.memory.long_term.forget(pending.payload["key"])
        runtime.audit.record("memory_delete", "completed", {"key": pending.payload["key"], "deleted": deleted})
        return {"completed": True, "deleted": deleted}

    # Real machine actions. These only run here -- after the user confirmed the
    # exact target that the brain proposed.
    operation = pending.payload.get("operation")
    if pending.action_type == ActionType.APP_OPEN and operation == "open_app":
        result = app_launcher.open_app(pending.payload["target"])
        runtime.audit.record("app_launch", "completed" if result.ok else "failed", result.to_dict())
        return {"completed": result.ok, **result.to_dict()}
    if pending.action_type == ActionType.APP_OPEN and operation == "open_website":
        result = app_launcher.open_website(pending.payload["target"])
        runtime.audit.record("web_open", "completed" if result.ok else "failed", result.to_dict())
        return {"completed": result.ok, **result.to_dict()}
    if pending.action_type == ActionType.SCREEN_CAPTURE and operation == "screenshot":
        path = runtime.settings.data_dir / "media" / "screenshot.png"
        message = runtime.desktop.screenshot(str(path))
        ok = path.exists()
        runtime.audit.record("screenshot", "completed" if ok else "failed", {"path": str(path)})
        return {"completed": ok, "detail": message, "path": str(path) if ok else None}

    raise HTTPException(status_code=400, detail="This confirmation belongs to a legacy or unsupported action.")


# ---- Media produced by the brain (searched or generated images) ----

@router.get("/media")
def list_media(limit: int = 30, kind: Optional[str] = None):
    return {"items": runtime.brain.media.recent(limit=max(1, min(limit, 100)), kind=kind)}


@router.get("/media/{media_id}")
def get_media(media_id: str):
    found = runtime.brain.media.get(media_id)
    if not found:
        raise HTTPException(status_code=404, detail="Media not found.")
    path, media_type = found
    return FileResponse(str(path), media_type=media_type)


class ImageSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=4, ge=1, le=10)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    size: int = Field(default=768, ge=256, le=1280)


@router.post("/media/search")
def search_images(request: ImageSearchRequest):
    result = runtime.brain.images.search(request.query, limit=request.limit)
    runtime.audit.record("image_search", "completed", {"query": request.query, "found": len(result["images"])})
    return result


@router.post("/media/generate")
def generate_image(request: ImageGenerateRequest):
    result = runtime.brain.generator.generate(request.prompt, size=request.size)
    runtime.audit.record("image_generate", "completed", {"engine": result.engine})
    return {"item": result.item.to_dict(), "engine": result.engine, "note": result.note}


class BrowseRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


@router.post("/web/read")
def read_web_page(request: BrowseRequest):
    page = web_research.extract_page(request.url)
    if not page.get("ok"):
        raise HTTPException(status_code=400, detail=page.get("error", "Could not fetch that page."))
    # extract_page reports `chars`; indexing it unconditionally used to turn any
    # shape drift into a 500 on an otherwise successful read.
    runtime.audit.record(
        "web_read",
        "completed",
        {"url": request.url, "chars": page.get("chars", len(page.get("text", "")))},
    )
    return page


@router.get("/launcher/status")
def launcher_status():
    return app_launcher.status()


@router.post("/vision/ocr")
def ocr_image(request: OCRRequest):
    encoded = request.image_base64.split(",", 1)[-1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="image_base64 must contain valid base64 image bytes.")
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        text = extract_text_from_image(tmp_path)
    except RuntimeError as exc:
        # OCR is optional: it needs the native tesseract binary, which most
        # machines do not have. extract_text_from_image raises RuntimeError
        # carrying the install command, and that used to escape as a bare 500 --
        # indistinguishable in the UI from "the server is broken", so the user
        # had no way to learn that one install fixes it.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        # Valid base64 that is not a decodable image.
        raise HTTPException(status_code=400, detail=f"That file could not be read as an image: {exc}") from exc
    finally:
        os.unlink(tmp_path)
    runtime.audit.record("vision_ocr", "completed", {"chars_extracted": len(text)})
    return {"text": text}


# ---- Companion device protocol (backend half only -- see companions/companions.py) ----

@router.post("/companions/pairing-code")
def create_pairing_code():
    code = runtime.companions.create_pairing_code()
    runtime.audit.record("companion", "pairing_code_created", {})
    return code


@router.post("/companions/pair")
def pair_companion(request: PairRequest):
    device = runtime.companions.pair(request.code, request.label, request.platform, request.capabilities)
    if not device:
        raise HTTPException(status_code=400, detail="Pairing code is invalid or expired.")
    runtime.audit.record("companion", "paired", {"device_id": device["device_id"], "platform": request.platform})
    return device


@router.get("/companions/devices")
def list_companion_devices(authorization: Optional[str] = Header(default=None)):
    _require_device(authorization)
    return {"devices": runtime.companions.devices()}


@router.post("/companions/events")
def record_companion_event(request: CompanionEventRequest, authorization: Optional[str] = Header(default=None)):
    device = _require_device(authorization)
    event = runtime.companions.record_event(device["id"], request.event_type, request.payload)
    runtime.audit.record("companion_event", "recorded", {"device_id": device["id"], "event_type": request.event_type})
    return event


# ---- Connectors ----

@router.get("/connectors")
def list_connectors():
    catalog = []
    for spec in CATALOG:
        status = runtime.connectors.status(spec)
        catalog.append({
            "id": spec.id,
            "name": spec.name,
            "category": spec.category,
            "summary": spec.summary,
            "docs_url": spec.docs_url,
            "note": spec.note,
            "connected": status["connected"],
            "from_environment": status.get("from_environment", False),
            "values": status.get("values", {}),
            "connected_at": status.get("connected_at"),
            "updated_at": status.get("updated_at"),
            "last_test": status.get("last_test"),
            "fields": [
                {"key": f.key, "label": f.label, "placeholder": f.placeholder,
                 "secret": f.secret, "required": f.required, "kind": f.kind, "help": f.help}
                for f in spec.fields
            ],
        })
    return {"connectors": catalog}


@router.post("/connectors/{connector_id}")
def save_connector(connector_id: str, request: ConnectorSaveRequest):
    spec = get_spec(connector_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")
    try:
        runtime.connectors.save(connector_id, request.values)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")
    if connector_id in {"openrouter", "cloud_llm"}:
        runtime.refresh_cloud_model()
    runtime.audit.record("connector", "saved", {"connector_id": connector_id})
    status = runtime.connectors.status(spec)
    return {"connector": status, "message": f"{spec.name} credentials saved."}


@router.post("/connectors/{connector_id}/test")
def test_connector(connector_id: str, request: ConnectorTestRequest):
    spec = get_spec(connector_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")
    if request.values:
        try:
            runtime.connectors.save(connector_id, request.values)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")
    if connector_id in {"openrouter", "cloud_llm"}:
        runtime.refresh_cloud_model()
    creds = runtime.connectors.credentials(connector_id)
    ok, message = verify_connector(connector_id, creds)
    runtime.connectors.record_test(connector_id, ok, message)
    return {"connector_id": connector_id, "ok": ok, "message": message}


@router.delete("/connectors/{connector_id}")
def delete_connector(connector_id: str):
    existed = runtime.connectors.delete(connector_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"No saved credentials for: {connector_id}")
    if connector_id in {"openrouter", "cloud_llm"}:
        runtime.refresh_cloud_model()
    runtime.audit.record("connector", "deleted", {"connector_id": connector_id})
    return {"deleted": True, "connector_id": connector_id}


# ---- Tools / Features Toggle ----

@router.get("/tools")
def list_tools():
    tools = []
    for metadata in runtime.capabilities.discover():
        for tool_id in metadata.legacy_ids or (metadata.name,):
            tools.append({
                "id": tool_id,
                "name": metadata.display_name or metadata.name.replace("_", " ").title(),
                "description": metadata.description,
                "category": metadata.category,
                "enabled": runtime.get_tool_enabled(tool_id),
            })
    return {"tools": tools, "categories": sorted(set(t["category"] for t in tools))}


@router.post("/tools/toggle")
def toggle_tool(request: ToolToggleRequest):
    try:
        metadata = runtime.capabilities.metadata(request.tool_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {request.tool_id}")
    runtime.set_tool_enabled(request.tool_id, request.enabled)
    runtime.audit.record("tool", "toggle", {"tool_id": request.tool_id, "enabled": request.enabled})
    return {
        "tool_id": request.tool_id,
        "enabled": request.enabled,
        "name": metadata.display_name or metadata.name.replace("_", " ").title(),
    }


# ---- Plugins (opt-in manifest only -- enabling ≠ a working OAuth connection) ----

@router.get("/plugins")
def list_plugins():
    return {"plugins": runtime.plugins.available()}


@router.post("/plugins/enable")
def enable_plugin(request: PluginEnableRequest):
    plugin = runtime.plugins.enable(request.identifier)
    if not plugin:
        raise HTTPException(status_code=404, detail="Unknown plugin identifier.")
    runtime.audit.record("plugin", "enabled", {"identifier": request.identifier})
    return plugin


# ---- Observability ----

@router.get("/system/status")
def system_status():
    return runtime.system_monitor.snapshot(runtime.settings.data_dir)


@router.get("/system/audit")
def audit_log(limit: int = 100):
    return {"entries": runtime.audit.recent(limit)}


# ---- Goal Manager ----

@router.post("/goals")
def create_goal(request: GoalCreateRequest):
    goal = runtime.goals.create(
        title=request.title,
        description=request.description,
        scope=GoalScope(request.scope),
        priority=GoalPriority(request.priority),
        parent_id=request.parent_id,
        target_date=request.target_date,
        metadata=request.metadata,
    )
    runtime.audit.record("goal", "created", {"goal_id": goal.id, "title": goal.title})
    return goal.to_dict()


@router.get("/goals")
def list_goals(scope: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    scope_enum = GoalScope(scope) if scope else None
    status_enum = GoalStatus(status) if status else None
    goals = runtime.goals.list_goals(scope=scope_enum, status=status_enum, limit=limit)
    return {"goals": [g.to_dict() for g in goals]}


@router.get("/goals/summary")
def goals_summary():
    return runtime.goals.status_summary()


@router.get("/goals/daily")
def daily_goals():
    return {"goals": [g.to_dict() for g in runtime.goals.get_daily()], "plan": runtime.goals.auto_plan_daily()}


@router.get("/goals/reminders")
def goal_reminders():
    return {"reminders": runtime.goals.get_due_reminders()}


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str):
    goal = runtime.goals.get(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return runtime.goals.get_hierarchy(goal_id)


@router.put("/goals/{goal_id}")
def update_goal(goal_id: str, request: GoalUpdateRequest):
    updates = {k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None}
    goal = runtime.goals.update(goal_id, **updates)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    runtime.audit.record("goal", "updated", {"goal_id": goal_id})
    return goal.to_dict()


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: str):
    deleted = runtime.goals.delete(goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found.")
    runtime.audit.record("goal", "deleted", {"goal_id": goal_id})
    return {"deleted": True, "goal_id": goal_id}


@router.post("/goals/{goal_id}/tasks")
def add_task_to_goal(goal_id: str, task_id: str):
    ok = runtime.goals.add_task(goal_id, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"added": True, "goal_id": goal_id, "task_id": task_id}


@router.post("/goals/{goal_id}/dependencies")
def add_dependency_to_goal(goal_id: str, dep_goal_id: str):
    ok = runtime.goals.add_dependency(goal_id, dep_goal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"added": True, "goal_id": goal_id, "dep_goal_id": dep_goal_id}


@router.post("/goals/{goal_id}/milestones")
def add_milestone_to_goal(goal_id: str, request: MilestoneRequest):
    milestone_id = runtime.goals.add_milestone(goal_id, request.title, request.target_date)
    if not milestone_id:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"milestone_id": milestone_id, "goal_id": goal_id, "title": request.title}


@router.put("/goals/{goal_id}/milestones/{milestone_id}/complete")
def complete_milestone(goal_id: str, milestone_id: str):
    ok = runtime.goals.complete_milestone(goal_id, milestone_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal or milestone not found.")
    return {"completed": True, "goal_id": goal_id, "milestone_id": milestone_id}


# ---- Decision Engine ----

@router.get("/decision/history")
def decision_history(limit: int = 20):
    return {"history": runtime.brain.decision_engine.get_history(limit)}


# ---- Reflection Engine ----

@router.get("/reflection/history")
def reflection_history(limit: int = 20):
    history = runtime.brain._reflect_history[-limit:] if hasattr(runtime.brain, "_reflect_history") else []
    return {"history": history, "total": len(runtime.brain._reflect_history) if hasattr(runtime.brain, "_reflect_history") else 0}


# ---- Agent Tasks ----

@router.get("/agents/tasks")
def list_agent_tasks(limit: int = 50):
    return {"tasks": runtime.tasks.list(limit)}

