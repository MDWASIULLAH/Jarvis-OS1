"""
api/routes.py

REST surface for the JARVIS backend. A future desktop/mobile client
(Electron, React Native, or the chat-UI demo artifact) talks to this over
localhost.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..brain.llm_interface import get_default_backend
from ..capabilities import fun_and_space, knowledge_apis, location_services, translate_currency
from ..capabilities.email_module import EmailModule
from ..capabilities.news_module import NewsModule
from ..capabilities.system_control import SystemControlModule
from ..capabilities.weather_module import WeatherModule
from ..memory.memory_store import MemorySystem
from ..security.permissions import SecurityGate

router = APIRouter()

DATA_DIR = Path.home() / ".jarvis"
memory = MemorySystem(DATA_DIR)
security = SecurityGate()
llm = get_default_backend()
email = EmailModule(security, llm.generate)
weather = WeatherModule()          # Open-Meteo by default, no key needed
news = NewsModule(api_key=None)    # RSS fallback by default, no key needed
system = SystemControlModule(security)


class ChatMessage(BaseModel):
    text: str


class ConfirmRequest(BaseModel):
    confirmation_id: str


class DraftRequest(BaseModel):
    to: str
    intent: str


@router.post("/chat")
def chat(msg: ChatMessage):
    memory.short_term.add("user", msg.text)
    reply = llm.generate(msg.text, system="You are JARVIS, a polite, loyal local assistant.")
    memory.short_term.add("jarvis", reply)
    return {"reply": reply}


@router.get("/memory/facts")
def list_facts():
    return memory.long_term.all_facts()


@router.post("/memory/forget/{key}")
def forget_fact(key: str):
    return {"forgotten": memory.long_term.forget(key)}


@router.post("/email/draft")
def draft_email(req: DraftRequest):
    draft = email.compose_draft(req.to, req.intent)
    return {"to": draft.to, "subject": draft.subject, "body": draft.body}


@router.post("/system/shutdown/request")
def shutdown_request():
    decision = system.request_shutdown()
    return decision.__dict__


@router.post("/system/shutdown/confirm")
def shutdown_confirm(req: ConfirmRequest):
    return {"result": system.execute_shutdown(req.confirmation_id)}


# ---- Free / keyless capability endpoints ----------------------------------

@router.get("/weather")
def get_weather(lat: float, lon: float):
    return {"summary": weather.current_weather(lat, lon)}


@router.get("/news/headlines")
def get_news(topic: str = "top", limit: int = 5):
    return {"summary": news.summarize(topic, limit)}


@router.get("/tools/define")
def get_definition(word: str):
    return {"result": knowledge_apis.define(word)}


@router.get("/tools/quick-answer")
def get_quick_answer(q: str):
    return {"result": knowledge_apis.quick_answer(q)}


@router.get("/tools/geocode")
def get_geocode(place: str):
    result = location_services.geocode(place)
    return result or {"error": "not found"}


@router.get("/tools/ip-info")
def get_ip_info(ip: Optional[str] = None):
    result = location_services.ip_info(ip)
    return result or {"error": "lookup failed"}


@router.get("/tools/space-news")
def get_space_news(limit: int = 5):
    return {"results": fun_and_space.space_news(limit)}


@router.get("/tools/tech-news")
def get_tech_news(limit: int = 5):
    return {"results": fun_and_space.top_tech_news(limit)}


@router.get("/tools/apod")
def get_apod():
    return fun_and_space.astronomy_picture_of_the_day() or {"error": "unavailable"}


@router.get("/tools/qr")
def get_qr(data: str, size: int = 200):
    return {"url": fun_and_space.qr_code_url(data, size)}


@router.get("/tools/currency")
def get_currency(amount: float, from_ccy: str, to_ccy: str):
    return {"result": translate_currency.convert_currency(amount, from_ccy, to_ccy)}


@router.post("/tools/translate")
def post_translate(text: str, target_lang: str, source_lang: str = "auto"):
    return {"result": translate_currency.translate(text, target_lang, source_lang)}
