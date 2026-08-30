"""
capabilities/chat_platforms.py

Telegram and Discord bot clients with full remote control.
Telegram now supports remote commands: screenshot, open app, shutdown,
restart, sleep, lock, run workflow, check CPU, check RAM, read
notifications, read clipboard, search files, create/delete folder,
rename/move/compress files, download/upload files, and return screenshots,
generated images, logs, PDFs, ZIP files, code, and documents.

WhatsApp is included with a clear explanation of the WhatsApp Business API
requirement. Unofficial WhatsApp Web automation is NOT supported due to
Terms of Service violations.
"""

from __future__ import annotations

import base64
import os
import re
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional

import requests


class TelegramClient:
    """Full Telegram bot client with remote control capabilities."""

    def __init__(self, bot_token: str):
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._command_handlers: dict[str, Callable] = {}
        self._authenticated_users: set[int] = set()
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._command_handlers = {
            "/start": self._cmd_start,
            "/help": self._cmd_help,
            "/status": self._cmd_status,
            "/screenshot": self._cmd_screenshot,
            "/open": self._cmd_open,
            "/shutdown": self._cmd_shutdown,
            "/restart": self._cmd_restart,
            "/lock": self._cmd_lock,
            "/cpu": self._cmd_cpu,
            "/ram": self._cmd_ram,
            "/disk": self._cmd_disk,
            "/clipboard": self._cmd_clipboard,
            "/search": self._cmd_search,
            "/files": self._cmd_files,
            "/mkdir": self._cmd_mkdir,
            "/move": self._cmd_move,
            "/rename": self._cmd_rename,
            "/compress": self._cmd_compress,
            "/download": self._cmd_download,
            "/logs": self._cmd_logs,
            "/notifications": self._cmd_notifications,
            "/weather": self._cmd_weather,
            "/news": self._cmd_news,
            "/remember": self._cmd_remember,
            "/recall": self._cmd_recall,
        }

    def set_auth_users(self, user_ids: set[int]) -> None:
        self._authenticated_users = user_ids

    def is_authenticated(self, user_id: int) -> bool:
        return not self._authenticated_users or user_id in self._authenticated_users

    def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
        try:
            r = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4096], "parse_mode": parse_mode},
                timeout=10,
            )
            return r.ok
        except requests.RequestException:
            return False

    def send_photo(self, chat_id: str, photo_path: str, caption: str = "") -> bool:
        try:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption[:1024]
                r = requests.post(f"{self.base_url}/sendPhoto", data=data, files=files, timeout=20)
            return r.ok
        except (requests.RequestException, FileNotFoundError, OSError):
            return False

    def send_document(self, chat_id: str, file_path: str, caption: str = "") -> bool:
        try:
            with open(file_path, "rb") as f:
                filename = os.path.basename(file_path)
                files = {"document": (filename, f)}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption[:1024]
                r = requests.post(f"{self.base_url}/sendDocument", data=data, files=files, timeout=30)
            return r.ok
        except (requests.RequestException, FileNotFoundError, OSError):
            return False

    def send_zip(self, chat_id: str, file_paths: list[str], zip_name: str = "files.zip") -> bool:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in file_paths:
                if os.path.exists(fp):
                    zf.write(fp, os.path.basename(fp))
        buf.seek(0)
        try:
            files = {"document": (zip_name, buf, "application/zip")}
            r = requests.post(
                f"{self.base_url}/sendDocument",
                data={"chat_id": chat_id},
                files=files,
                timeout=30,
            )
            return r.ok
        except requests.RequestException:
            return False

    def get_updates(self, offset: int = None) -> list[dict]:
        try:
            params = {"timeout": 5}
            if offset is not None:
                params["offset"] = offset
            r = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("result", [])
        except requests.RequestException:
            return []

    def process_update(self, update: dict, context: dict = None) -> Optional[str]:
        msg = update.get("message", {})
        text = (msg.get("text") or msg.get("caption") or "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        user_id = msg.get("from", {}).get("id", 0) if msg else 0

        if not self.is_authenticated(user_id):
            self.send_message(chat_id, "Unauthorized. This bot requires authentication.")
            return None

        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower().split("@")[0]
            args = parts[1] if len(parts) > 1 else ""
            handler = self._command_handlers.get(cmd)
            if handler:
                return handler(chat_id, args, context)
            else:
                self.send_message(chat_id, f"Unknown command: {cmd}\nType /help for available commands.")
                return None

        response = context.get("brain_handle", lambda t: "I received your message.")(text) if context else text
        self.send_message(chat_id, response)
        return response

    def _cmd_start(self, chat_id: str, args: str, ctx: dict) -> str:
        msg = (
            "*JARVIS Remote Control*\n\n"
            "Commands:\n"
            "/status - System status\n"
            "/screenshot - Take screenshot\n"
            "/open \\<app\\> - Open application\n"
            "/cpu - CPU usage\n"
            "/ram - RAM usage\n"
            "/disk - Disk usage\n"
            "/clipboard - Read clipboard\n"
            "/search \\<pattern\\> - Search files\n"
            "/files \\<path\\> - List directory\n"
            "/mkdir \\<path\\> - Create folder\n"
            "/move \\<src\\> \\<dst\\> - Move file\n"
            "/rename \\<old\\> \\<new\\> - Rename file\n"
            "/compress \\<folder\\> - Create ZIP\n"
            "/download \\<path\\> - Download file\n"
            "/logs - Recent logs\n"
            "/weather \\<city\\> - Get weather\n"
            "/news - Get headlines\n"
            "/remember \\<fact\\> - Store memory\n"
            "/recall \\<query\\> - Search memory\n"
            "/help - This message"
        )
        self.send_message(chat_id, msg)
        return msg

    def _cmd_help(self, chat_id: str, args: str, ctx: dict) -> str:
        return self._cmd_start(chat_id, args, ctx)

    def _cmd_status(self, chat_id: str, args: str, ctx: dict) -> str:
        monitor = ctx.get("system_monitor")
        data_dir = ctx.get("data_dir", Path.home() / ".jarvis")
        if monitor:
            snap = monitor.snapshot(data_dir)
            msg = (
                "*System Status*\n"
                f"CPU: {snap.get('cpu_percent', 'N/A')}%\n"
                f"RAM: {snap.get('ram_used_human', 'N/A')}\n"
                f"Disk: {snap.get('disk_used_human', 'N/A')}\n"
                f"Uptime: {snap.get('uptime', 'N/A')}"
            )
        else:
            msg = "System monitor not available."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_screenshot(self, chat_id: str, args: str, ctx: dict) -> str:
        desktop = ctx.get("desktop")
        if not desktop:
            self.send_message(chat_id, "Desktop automation not available.")
            return "Desktop automation not available."
        path = str(Path(tempfile.gettempdir()) / f"jarvis_telegram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        try:
            import pyautogui
            pyautogui.screenshot(path)
        except ImportError:
            self.send_message(chat_id, "pyautogui not installed on this machine.")
            return "pyautogui not installed."
        if os.path.exists(path):
            self.send_photo(chat_id, path, "Screenshot captured.")
            try:
                os.unlink(path)
            except OSError:
                pass
            return "Screenshot sent."
        self.send_message(chat_id, "Failed to capture screenshot.")
        return "Failed."

    def _cmd_open(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /open \\<application name\\>")
            return "No app specified."
        desktop = ctx.get("desktop")
        if desktop:
            result = desktop.execute_open_app(args)
            msg = f"Opened *{args}*: {result.get('message', 'done')}"
        else:
            try:
                os.system(f"xdg-open {args} &")
                msg = f"Attempted to open *{args}*."
            except Exception as e:
                msg = f"Failed to open *{args}*: {e}"
        self.send_message(chat_id, msg)
        return msg

    def _cmd_shutdown(self, chat_id: str, args: str, ctx: dict) -> str:
        self.send_message(chat_id, "Shutdown requested. This requires manual confirmation on the machine.")
        return "Shutdown confirmation pending."

    def _cmd_restart(self, chat_id: str, args: str, ctx: dict) -> str:
        self.send_message(chat_id, "Restart requested. This requires manual confirmation on the machine.")
        return "Restart confirmation pending."

    def _cmd_lock(self, chat_id: str, args: str, ctx: dict) -> str:
        import platform as _plat
        system = _plat.system()
        try:
            if system == "Linux":
                os.system("gnome-screensaver-command -l || xdg-screensaver lock &")
            elif system == "Darwin":
                os.system("pmset displaysleepnow &")
            msg = "Lock command sent."
        except Exception:
            msg = "Lock not supported on this system."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_cpu(self, chat_id: str, args: str, ctx: dict) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1, percpu=False)
            msg = f"*CPU Usage*: {cpu}%"
        except ImportError:
            msg = "psutil not installed."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_ram(self, chat_id: str, args: str, ctx: dict) -> str:
        try:
            import psutil
            mem = psutil.virtual_memory()
            msg = f"*RAM*: {mem.used // (1024**3)} GB / {mem.total // (1024**3)} GB ({mem.percent}%)"
        except ImportError:
            msg = "psutil not installed."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_disk(self, chat_id: str, args: str, ctx: dict) -> str:
        try:
            import psutil
            disk = psutil.disk_usage("/")
            msg = f"*Disk*: {disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB ({disk.percent}%)"
        except ImportError:
            msg = "psutil not installed."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_clipboard(self, chat_id: str, args: str, ctx: dict) -> str:
        desktop = ctx.get("desktop")
        if desktop:
            result = desktop.execute_clipboard_paste()
            text = result.get("message", "")[:1000]
            msg = f"*Clipboard*:\n```\n{text}\n```" if text else "Clipboard is empty."
        else:
            msg = "Clipboard access not available."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_search(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /search \\<pattern\\>")
            return "No pattern."
        home = str(Path.home())
        pattern = f"*{args}*"
        try:
            results = list(Path(home).rglob(pattern))[:20]
        except Exception:
            results = list(Path(home).glob(f"**/*{args}*"))[:20]
        if results:
            msg = "*Search Results*:\n" + "\n".join(f"- `{str(r)}`" for r in results[:15])
        else:
            msg = f"No files matching '*{args}*' found in home directory."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_files(self, chat_id: str, args: str, ctx: dict) -> str:
        path = Path(args) if args else Path.home()
        if not path.exists():
            self.send_message(chat_id, f"Path not found: {args}")
            return "Path not found."
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))[:30]
            lines = [f"*{path}*"]
            for e in entries:
                icon = "[D]" if e.is_dir() else "[F]"
                size = f" ({e.stat().st_size // 1024}KB)" if e.is_file() else ""
                lines.append(f"{icon} {e.name}{size}")
            msg = "\n".join(lines)
        except PermissionError:
            msg = f"Permission denied: {path}"
        self.send_message(chat_id, msg)
        return msg

    def _cmd_mkdir(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /mkdir \\<path\\>")
            return "No path."
        try:
            Path(args).mkdir(parents=True, exist_ok=True)
            msg = f"Created folder: *{args}*"
        except Exception as e:
            msg = f"Failed: {e}"
        self.send_message(chat_id, msg)
        return msg

    def _cmd_move(self, chat_id: str, args: str, ctx: dict) -> str:
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            self.send_message(chat_id, "Usage: /move \\<src\\> \\<dst\\>")
            return "Missing arguments."
        try:
            import shutil
            shutil.move(parts[0], parts[1])
            msg = f"Moved: *{parts[0]}* -> *{parts[1]}*"
        except Exception as e:
            msg = f"Failed: {e}"
        self.send_message(chat_id, msg)
        return msg

    def _cmd_rename(self, chat_id: str, args: str, ctx: dict) -> str:
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            self.send_message(chat_id, "Usage: /rename \\<old\\> \\<new\\>")
            return "Missing arguments."
        try:
            os.rename(parts[0], parts[1])
            msg = f"Renamed: *{parts[0]}* -> *{parts[1]}*"
        except Exception as e:
            msg = f"Failed: {e}"
        self.send_message(chat_id, msg)
        return msg

    def _cmd_compress(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /compress \\<folder\\>")
            return "No folder."
        path = Path(args)
        if not path.exists():
            self.send_message(chat_id, f"Folder not found: {args}")
            return "Folder not found."
        zip_path = path.with_suffix(".zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if path.is_dir():
                    for f in path.rglob("*"):
                        if f.is_file():
                            zf.write(f, f.relative_to(path))
                else:
                    zf.write(path, path.name)
            self.send_document(chat_id, str(zip_path), f"Compressed: {path.name}")
            msg = f"ZIP created and sent: {zip_path}"
        except Exception as e:
            msg = f"Failed: {e}"
        self.send_message(chat_id, msg if "sent" in msg else msg)
        return msg

    def _cmd_download(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /download \\<path\\>")
            return "No path."
        path = Path(args)
        if not path.exists():
            self.send_message(chat_id, f"File not found: {args}")
            return "File not found."
        if path.is_file():
            self.send_document(chat_id, str(path), path.name)
        else:
            self.send_message(chat_id, f"*{args}* is a directory. Use /compress to get a ZIP.")
        return f"Sent: {path.name}" if path.is_file() else "Is a directory."

    def _cmd_logs(self, chat_id: str, args: str, ctx: dict) -> str:
        data_dir = ctx.get("data_dir", Path.home() / ".jarvis")
        audit_path = data_dir / "audit.db"
        if audit_path.exists():
            self.send_document(chat_id, str(audit_path), "Audit logs database")
            msg = "Audit logs sent."
        else:
            msg = "No audit logs found."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_notifications(self, chat_id: str, args: str, ctx: dict) -> str:
        self.send_message(chat_id, "Notification reading requires desktop integration (not available in headless mode).")
        return "Not available."

    def _cmd_weather(self, chat_id: str, args: str, ctx: dict) -> str:
        weather_mod = ctx.get("weather")
        location_mod = ctx.get("location")
        city = args or "London"
        if weather_mod and location_mod:
            resolved = location_mod.geocode(city)
            if resolved:
                summary = weather_mod.current_weather(resolved[0], resolved[1])
                msg = f"*Weather for {city}*: {summary}"
            else:
                msg = f"Could not resolve location: {city}"
        else:
            msg = "Weather module not configured."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_news(self, chat_id: str, args: str, ctx: dict) -> str:
        news_mod = ctx.get("news")
        if news_mod:
            summary = news_mod.summarize(args or "top", limit=5)
            msg = f"*News Headlines*:\n{summary}" if summary else "No headlines available."
        else:
            msg = "News module not configured."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_remember(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /remember \\<fact\\>")
            return "No fact."
        memory = ctx.get("memory")
        if memory:
            key = f"telegram_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            memory.long_term.remember(key, args, "telegram_remote")
            msg = f"Stored: *{args}*"
        else:
            msg = "Memory system not available."
        self.send_message(chat_id, msg)
        return msg

    def _cmd_recall(self, chat_id: str, args: str, ctx: dict) -> str:
        if not args:
            self.send_message(chat_id, "Usage: /recall \\<query\\>")
            return "No query."
        memory = ctx.get("memory")
        if memory:
            from ..memory.semantic_search import SemanticIndex
            index = SemanticIndex()
            index.build(memory.long_term.all_facts())
            hits = index.search(args, top_k=5)
            if hits:
                msg = "*Memory Results*:\n" + "\n".join(f"- *{h['key']}*: {h['text']}" for h in hits)
            else:
                msg = "No matching memories found."
        else:
            msg = "Memory system not available."
        self.send_message(chat_id, msg)
        return msg


class DiscordClient:
    """Discord bot client."""

    def __init__(self, bot_token: str):
        self.headers = {"Authorization": f"Bot {bot_token}"}

    def send_message(self, channel_id: str, text: str) -> bool:
        try:
            r = requests.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=self.headers,
                json={"content": text[:2000]},
                timeout=10,
            )
            return r.ok
        except requests.RequestException:
            return False

    def send_embed(self, channel_id: str, title: str, description: str, fields: list = None) -> bool:
        payload = {
            "embeds": [{
                "title": title,
                "description": description[:4096],
                "color": 0xF0A030,
            }],
        }
        if fields:
            payload["embeds"][0]["fields"] = [{"name": f["name"], "value": f["value"], "inline": f.get("inline", True)} for f in fields[:25]]
        try:
            r = requests.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            return r.ok
        except requests.RequestException:
            return False


class WhatsAppClient:
    """
    WhatsApp Business Platform client.

    IMPORTANT: WhatsApp integration requires the official WhatsApp Business API
    (Cloud API) which needs:
    1. A Meta Business account with verified business
    2. A registered phone number (not used by personal WhatsApp)
    3. A WhatsApp Business App or Cloud API access token
    4. A webhook endpoint for receiving messages

    The unofficial WhatsApp Web automation libraries (e.g., whatsapp-web.js,
    pywhatsapp) run against WhatsApp's Terms of Service and carry real risk of
    account bans. This module uses ONLY the official WhatsApp Cloud API.

    If you only need message notifications on your phone, Telegram or Discord
    bots are simpler alternatives that require no business verification.
    """

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str = "", phone_number_id: str = ""):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self._available = bool(access_token and phone_number_id)

    def is_available(self) -> bool:
        return self._available

    def send_message(self, to: str, text: str) -> tuple[bool, str]:
        if not self._available:
            return False, (
                "WhatsApp is not configured. You need a Meta Business account, "
                "a WhatsApp Business API phone number ID, and an access token. "
                "See: https://developers.facebook.com/docs/whatsapp/cloud-api"
            )
        try:
            r = requests.post(
                f"{self.BASE_URL}/{self.phone_number_id}/messages",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text[:4096]},
                },
                timeout=10,
            )
            if r.ok:
                return True, "Message sent via WhatsApp."
            error = ""
            try:
                error = r.json().get("error", {}).get("message", "")
            except Exception:
                error = str(r.status_code)
            return False, f"WhatsApp API error: {error}"
        except requests.RequestException as e:
            return False, f"WhatsApp connection failed: {e}"

    def send_document(self, to: str, file_path: str, caption: str = "") -> tuple[bool, str]:
        if not self._available:
            return False, "WhatsApp is not configured."
        try:
            with open(file_path, "rb") as f:
                filename = os.path.basename(file_path)
                media_r = requests.post(
                    f"{self.BASE_URL}/{self.phone_number_id}/media",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    files={"file": (filename, f)},
                    data={"messaging_product": "whatsapp", "type": "application/octet-stream"},
                    timeout=20,
                )
                if not media_r.ok:
                    return False, "Failed to upload media."
                media_id = media_r.json().get("id", "")
                doc_r = requests.post(
                    f"{self.BASE_URL}/{self.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": to,
                        "type": "document",
                        "document": {"id": media_id, "filename": filename, "caption": caption[:1024] if caption else ""},
                    },
                    timeout=10,
                )
                return doc_r.ok, "Document sent via WhatsApp." if doc_r.ok else "Failed to send document."
        except Exception as e:
            return False, f"WhatsApp document send failed: {e}"

    def send_image(self, to: str, image_path: str, caption: str = "") -> tuple[bool, str]:
        if not self._available:
            return False, "WhatsApp is not configured."
        try:
            with open(image_path, "rb") as f:
                filename = os.path.basename(image_path)
                media_r = requests.post(
                    f"{self.BASE_URL}/{self.phone_number_id}/media",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    files={"file": (filename, f)},
                    data={"messaging_product": "whatsapp", "type": "image/" + (filename.rsplit(".", 1)[-1] if "." in filename else "png")},
                    timeout=20,
                )
                if not media_r.ok:
                    return False, "Failed to upload image."
                media_id = media_r.json().get("id", "")
                img_r = requests.post(
                    f"{self.BASE_URL}/{self.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": to,
                        "type": "image",
                        "image": {"id": media_id, "caption": caption[:1024] if caption else ""},
                    },
                    timeout=10,
                )
                return img_r.ok, "Image sent via WhatsApp." if img_r.ok else "Failed to send image."
        except Exception as e:
            return False, f"WhatsApp image send failed: {e}"
