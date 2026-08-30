"""
capabilities/image_pipeline.py

Image retrieval + image generation, both landing in the same MediaStore so
the chat UI renders them identically.

RETRIEVAL ("show me pictures of Mount Everest", "who is SRK? show his image")
    query cleanup -> Wikipedia article images -> Wikimedia Commons search ->
    Openverse search -> download -> cache -> return media metadata.
    Sources are keyless and openly licensed, and every item keeps its
    source URL so the UI can credit it.

GENERATION ("make a logo", "generate a wallpaper of Iceland")
    If the owner configured a real image endpoint (JARVIS_IMAGE_API_URL,
    OpenAI-images-compatible or Automatic1111/ComfyUI-style), that is used.
    Otherwise JARVIS tries Pollinations.ai (free, no key, FLUX model) for
    photorealistic images of people and scenes. On failure, it falls back to
    a local Pillow procedural renderer.

    That local renderer is honestly described everywhere as procedural art,
    not a diffusion model. It exists so "generate an image" produces a real
    file you can see and download on a laptop with no GPU and no API key,
    instead of an apology.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import os
import random
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from . import web_research
from .media_store import MediaItem, MediaStore

_STOPWORDS = {
    "show", "me", "a", "an", "the", "of", "his", "her", "their", "some", "few",
    "please", "images", "image", "picture", "pictures", "pic", "pics", "photo",
    "photos", "photograph", "gallery", "find", "get", "send", "display", "see",
    "want", "to", "i", "you", "can", "could", "jarvis", "for", "what", "does",
    "look", "like", "give", "and", "with", "in", "on", "is", "who", "generate",
    "create", "make", "draw", "paint", "design", "render", "visualize",
    "visualise", "sketch", "wallpaper", "poster", "logo", "art", "digital",
    "now", "quickly", "thanks", "ai", "of", "about", "hey", "ok",
}

_STYLE_HINTS = {
    "neon": ((10, 12, 40), (255, 42, 160), (0, 240, 255)),
    "sunset": ((36, 12, 30), (255, 94, 58), (255, 200, 87)),
    "ocean": ((5, 24, 48), (0, 132, 176), (126, 234, 216)),
    "forest": ((12, 32, 20), (34, 120, 68), (186, 226, 120)),
    "mono": ((18, 18, 20), (90, 90, 96), (232, 232, 236)),
    "gold": ((26, 18, 6), (168, 112, 22), (255, 214, 128)),
    "cyber": ((8, 8, 22), (98, 32, 190), (0, 255, 208)),
    "pastel": ((250, 240, 236), (240, 170, 170), (150, 200, 220)),
    "neutral": ((14, 16, 22), (196, 132, 46), (255, 206, 128)),
}


@dataclass
class GenerationResult:
    item: MediaItem
    engine: str
    prompt: str
    note: str


# --------------------------------------------------------------- helpers

def clean_query(text: str) -> str:
    """Turn a conversational request into a searchable subject."""
    lowered = re.sub(r"[^\w\s'-]", " ", text.lower())
    lowered = re.sub(
        r"\b(show|send|find|get|give)\s+me\b|\bi\s+want\s+to\s+see\b|\bwhat\s+does\b|\blook\s+like\b",
        " ",
        lowered,
    )
    words = [w for w in lowered.split() if w and w not in _STOPWORDS]
    return " ".join(words).strip() or text.strip()


def _palette(prompt: str) -> tuple[tuple[int, int, int], ...]:
    lowered = prompt.lower()
    for hint, palette in _STYLE_HINTS.items():
        if hint in lowered:
            return palette
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    keys = list(_STYLE_HINTS)
    return _STYLE_HINTS[keys[seed % len(keys)]]


# ------------------------------------------------------------- retrieval

class ImageRetriever:
    """Finds real images for a subject and caches them locally."""

    def __init__(self, store: MediaStore):
        self.store = store

    def search(self, query: str, limit: int = 4, download_limit: Optional[int] = None) -> dict:
        subject = clean_query(query)
        candidates: list[dict] = []
        sources_tried: list[str] = []

        article = web_research.wikipedia_summary(subject)
        if article:
            sources_tried.append("wikipedia")
            if article.thumbnail:
                candidates.append(
                    {
                        "url": article.thumbnail,
                        "caption": article.title,
                        "media_type": "image/jpeg",
                        "source": "wikipedia",
                        "source_url": article.url,
                    }
                )
            candidates += web_research.wikipedia_page_images(article.title, limit=limit)

        if len(candidates) < limit:
            sources_tried.append("wikimedia_commons")
            candidates += web_research.commons_search_images(subject, limit=limit)
        if len(candidates) < limit:
            sources_tried.append("openverse")
            candidates += web_research.openverse_search_images(subject, limit=limit)

        seen: set[str] = set()
        deduped = []
        for candidate in candidates:
            if candidate["url"] in seen:
                continue
            seen.add(candidate["url"])
            deduped.append(candidate)

        wanted = download_limit or limit
        items: list[dict] = []
        for candidate in deduped:
            if len(items) >= wanted:
                break
            downloaded = web_research.download(candidate["url"])
            if not downloaded:
                continue
            raw, media_type = downloaded
            if not media_type.startswith("image/"):
                media_type = candidate.get("media_type", "image/jpeg")
            item = self.store.save_bytes(
                raw,
                media_type=media_type,
                kind="image",
                caption=candidate.get("caption") or subject,
                source=candidate.get("source", "web"),
                source_url=candidate.get("source_url") or candidate["url"],
                width=candidate.get("width"),
                height=candidate.get("height"),
            )
            items.append(item.to_dict())

        return {
            "subject": subject,
            "images": items,
            "found": len(deduped),
            "sources_tried": sources_tried,
            "article": article.to_dict() if article else None,
        }


# ------------------------------------------------------------ prompt enhancer

_PEOPLE_KEYWORDS = re.compile(
    r"\b(?:person|people|man|woman|boy|girl|child|baby|guy|lady|gentleman|human|face|portrait|body|figure)\b",
    re.I,
)

_QUALITY_SUFFIX = ", high quality, photorealistic, detailed, 8k, sharp focus, professional lighting"


def _enhance_prompt(prompt: str) -> str:
    """Append quality keywords for people/portrait prompts to improve output."""
    enhanced = prompt.strip()
    if _PEOPLE_KEYWORDS.search(prompt) and len(enhanced) < 400:
        enhanced += _QUALITY_SUFFIX
    return enhanced


# ------------------------------------------------------------ generation

class ImageGenerator:
    """External endpoint when configured; local procedural renderer always."""

    def __init__(self, store: MediaStore, api_url: Optional[str] = None,
                 api_key: Optional[str] = None, model: Optional[str] = None):
        self.store = store
        self.api_url = (api_url or os.getenv("JARVIS_IMAGE_API_URL") or "").rstrip("/") or None
        self.api_key = api_key or os.getenv("JARVIS_IMAGE_API_KEY") or None
        self.model = model or os.getenv("JARVIS_IMAGE_MODEL") or "default"

    # ---- public

    def generate(self, prompt: str, size: int = 768) -> GenerationResult:
        if self.api_url:
            remote = self._generate_remote(prompt, size)
            if remote:
                return remote
        free = self._generate_free(prompt, size)
        if free:
            return free
        return self._generate_local(prompt, size)

    def available_engine(self) -> str:
        """Name of the active generation backend for the UI."""
        if self.api_url:
            return "external_api"
        try:
            import requests as _r
            resp = _r.get("https://image.pollinations.ai/ping", timeout=3)
            if resp.status_code == 200:
                return "pollinations_free"
        except Exception:
            pass
        return "local_procedural"

    # ---- free cloud API

    def _generate_free(self, prompt: str, size: int) -> Optional[GenerationResult]:
        """Try Pollinations.ai -- free, no key, no signup, uses FLUX model.

        Downloads image bytes, saves locally, and returns a cached URL so the
        frontend always gets a working /v1/media/... path.
        """
        enhanced = _enhance_prompt(prompt)
        encoded = quote(enhanced, safe="")
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={size}&height={size}&nologo=true&model=flux"
        try:
            resp = requests.get(url, timeout=90, allow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            item = self.store.save_bytes(
                resp.content, media_type=content_type, kind="image",
                caption=prompt[:160], source="pollinations_ai",
            )
            return GenerationResult(item, "pollinations_free", prompt,
                                    f"Generated via Pollinations.ai (free, FLUX model). Prompt: \"{enhanced}\"")
        except (requests.RequestException, ValueError):
            return None

    # ---- remote

    def _generate_remote(self, prompt: str, size: int) -> Optional[GenerationResult]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "n": 1,
                    "size": f"{size}x{size}",
                    "response_format": "b64_json",
                },
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None

        encoded = None
        if isinstance(payload.get("data"), list) and payload["data"]:
            first = payload["data"][0]
            encoded = first.get("b64_json")
            if not encoded and first.get("url"):
                downloaded = web_research.download(first["url"])
                if downloaded:
                    item = self.store.save_bytes(
                        downloaded[0], media_type=downloaded[1], kind="image",
                        caption=prompt[:160], source="image_api",
                    )
                    return GenerationResult(item, "external_api", prompt, "Generated by the configured image endpoint.")
        if not encoded and isinstance(payload.get("images"), list) and payload["images"]:
            encoded = payload["images"][0]  # Automatic1111 / ComfyUI style
        if not encoded:
            return None
        try:
            raw = base64.b64decode(re.sub(r"^data:image/\w+;base64,", "", encoded))
        except (ValueError, TypeError):
            return None
        item = self.store.save_bytes(raw, media_type="image/png", kind="image",
                                    caption=prompt[:160], source="image_api")
        return GenerationResult(item, "external_api", prompt, "Generated by the configured image endpoint.")

    # ---- local procedural renderer

    def _generate_local(self, prompt: str, size: int) -> GenerationResult:
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont
        except ImportError:
            raise RuntimeError("Pillow is required for local image generation (pip install pillow).")

        seed = int(hashlib.sha256(prompt.lower().encode("utf-8")).hexdigest()[:12], 16)
        rng = random.Random(seed)
        background, mid, accent = _palette(prompt)
        lowered = prompt.lower()
        wants_text = any(word in lowered for word in ("logo", "poster", "banner", "wallpaper with text", "title", "cover"))

        image = Image.new("RGB", (size, size), background)
        draw = ImageDraw.Draw(image, "RGBA")

        # Vertical gradient field.
        for y in range(size):
            ratio = y / max(1, size - 1)
            eased = ratio ** 1.35
            color = tuple(
                int(background[i] + (mid[i] - background[i]) * eased) for i in range(3)
            )
            draw.line([(0, y), (size, y)], fill=color)

        # Concentric light rings -- the "arc reactor" motif of the UI.
        centre = (rng.randint(size // 3, 2 * size // 3), rng.randint(size // 3, 2 * size // 3))
        for index in range(14, 0, -1):
            radius = int(size * 0.07 * index * rng.uniform(0.9, 1.05))
            alpha = max(6, 70 - index * 4)
            draw.ellipse(
                [centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius],
                outline=accent + (alpha,),
                width=max(1, size // 320),
            )

        # Organic ridge line -- reads as terrain/skyline depending on palette.
        points = []
        amplitude = size * rng.uniform(0.06, 0.14)
        offset = rng.uniform(0, 6.28)
        for x in range(0, size + 1, max(2, size // 160)):
            t = x / size
            y = (
                size * 0.68
                + math.sin(t * 6.28 * rng.uniform(0.8, 1.4) + offset) * amplitude
                + math.sin(t * 18.0 + offset * 2) * amplitude * 0.22
            )
            points.append((x, y))
        draw.polygon(points + [(size, size), (0, size)], fill=accent + (46,))
        draw.line(points, fill=accent + (170,), width=max(2, size // 240))

        # Particles.
        for _ in range(int(size * 0.42)):
            x, y = rng.randint(0, size), rng.randint(0, size)
            radius = rng.choice([1, 1, 1, 2, 2, 3])
            draw.ellipse([x, y, x + radius, y + radius], fill=accent + (rng.randint(60, 200),))

        image = image.filter(ImageFilter.SMOOTH_MORE)
        draw = ImageDraw.Draw(image, "RGBA")

        if wants_text:
            words = [w for w in re.sub(r"[^\w\s]", " ", prompt).split() if w.lower() not in _STOPWORDS]
            headline = " ".join(words[:3]).upper() or "JARVIS"
            font = self._font(int(size * 0.11))
            box = draw.textbbox((0, 0), headline, font=font)
            position = ((size - (box[2] - box[0])) // 2, int(size * 0.44))
            draw.text((position[0] + 3, position[1] + 3), headline, font=font, fill=(0, 0, 0, 120))
            draw.text(position, headline, font=font, fill=(255, 255, 255, 235))
            subtitle = " ".join(words[3:8]).title()
            if subtitle:
                small = self._font(int(size * 0.035))
                sbox = draw.textbbox((0, 0), subtitle, font=small)
                draw.text(
                    ((size - (sbox[2] - sbox[0])) // 2, position[1] + int(size * 0.13)),
                    subtitle, font=small, fill=accent + (230,),
                )

        # Signature so a generated image is never mistaken for a photograph.
        label = self._font(max(11, int(size * 0.022)))
        draw.text((14, size - int(size * 0.042)), "JARVIS · procedural render", font=label, fill=(255, 255, 255, 130))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        item = self.store.save_bytes(
            buffer.getvalue(),
            media_type="image/png",
            kind="image",
            caption=prompt[:160],
            source="local_procedural",
            width=size,
            height=size,
        )
        return GenerationResult(
            item,
            "local_procedural",
            prompt,
            "Rendered locally with a procedural generator (offline, no GPU). "
            "Set JARVIS_IMAGE_API_URL for photorealistic diffusion output.",
        )

    @staticmethod
    def _font(size: int):
        from PIL import ImageFont

        for candidate in (
            # Debian/Ubuntu
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # Fedora/RHEL/Amazon Linux put DejaVu somewhere else entirely
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            # macOS
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            # Windows
            "C:/Windows/Fonts/arialbd.ttf",
        ):
            try:
                return ImageFont.truetype(candidate, size)
            except (OSError, ImportError):
                continue

        # Last resort before the bitmap default: ask the OS where its fonts are.
        # The hardcoded list above misses distro-specific layouts, and the bitmap
        # fallback renders text so tightly that words run together.
        try:
            import glob

            for pattern in (
                "/usr/share/fonts/**/DejaVuSans*.ttf",
                "/usr/share/fonts/**/*.ttf",
                "/usr/local/share/fonts/**/*.ttf",
            ):
                for match in sorted(glob.glob(pattern, recursive=True)):
                    try:
                        return ImageFont.truetype(match, size)
                    except (OSError, ImportError):
                        continue
        except Exception:
            pass

        return ImageFont.load_default()
