"""
capabilities/desktop_automation.py v2

Full desktop control: Windows/Mac/Linux automation.
Open, close, minimize, maximize, create folder, rename, delete,
move, copy, paste, search, open PDF, browser, control volume,
brightness, media, screenshot, clipboard, camera, microphone,
explorer, recycle bin, downloads -- all gated through security.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ..security.permissions import ActionDecision, ActionType, SecurityGate

_OS_NAME = platform.system()


def _run(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip() or "ok"
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "command timed out"
    except Exception as exc:
        return False, str(exc)


class DesktopAutomationModule:
    def __init__(self, security: SecurityGate):
        self.security = security

    # ---- app operations

    def request_open_app(self, app_name: str) -> ActionDecision:
        return self.security.check_action(ActionType.APP_OPEN, target=app_name, payload={"operation": "open_app", "target": app_name})

    def execute_open_app(self, app_name: str) -> dict:
        if _OS_NAME == "Darwin":
            ok, msg = _run(["open", "-a", app_name])
        elif _OS_NAME == "Windows":
            ok, msg = _run(["start", "", app_name], timeout=5)
        else:
            ok, msg = _run(["which", app_name], timeout=3)
            if ok:
                ok, msg = _run([app_name], timeout=3)
            else:
                ok, msg = _run(["xdg-open", app_name], timeout=3)
        return {"ok": ok, "message": msg, "app": app_name}

    def execute_close_app(self, app_name: str) -> dict:
        if _OS_NAME == "Darwin":
            ok, msg = _run(["osascript", "-e", f'quit app "{app_name}"'])
        elif _OS_NAME == "Windows":
            ok, msg = _run(["taskkill", "/IM", f"{app_name}.exe", "/F"])
        else:
            ok, msg = _run(["pkill", "-f", app_name])
        return {"ok": ok, "message": msg, "app": app_name}

    # ---- web

    def request_open_website(self, url: str) -> ActionDecision:
        return self.security.check_action(ActionType.APP_OPEN, target=url, payload={"operation": "open_website", "target": url})

    def execute_open_website(self, url: str) -> dict:
        ok, msg = _run(["xdg-open", url], timeout=5)
        return {"ok": ok, "message": msg, "url": url}

    # ---- file operations

    def request_file_action(self, operation: str, target: str, destination: str = "") -> ActionDecision:
        return self.security.check_action(
            ActionType.FILE_DELETE if operation in ("delete", "rm") else ActionType.FILE_WRITE,
            target=target,
            payload={"operation": operation, "target": target, "destination": destination},
        )

    def execute_create_folder(self, path: str) -> dict:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return {"ok": True, "message": f"Created folder: {path}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def execute_rename(self, old_path: str, new_path: str) -> dict:
        try:
            os.rename(old_path, new_path)
            return {"ok": True, "message": f"Renamed: {old_path} -> {new_path}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def execute_delete(self, path: str) -> dict:
        try:
            p = Path(path)
            if p.is_dir():
                shutil.rmtree(path)
            else:
                p.unlink()
            return {"ok": True, "message": f"Deleted: {path}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def execute_move(self, src: str, dst: str) -> dict:
        try:
            shutil.move(src, dst)
            return {"ok": True, "message": f"Moved: {src} -> {dst}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def execute_copy(self, src: str, dst: str) -> dict:
        try:
            if Path(src).is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return {"ok": True, "message": f"Copied: {src} -> {dst}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def execute_search_files(self, directory: str, pattern: str) -> dict:
        try:
            results = list(Path(directory).rglob(pattern))[:50]
            return {"ok": True, "message": f"Found {len(results)} files",
                    "results": [str(p) for p in results]}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def execute_open_pdf(self, path: str) -> dict:
        return self.execute_open_website(f"file://{os.path.abspath(path)}")

    # ---- system control

    def request_system_action(self, operation: str, value: str = "") -> ActionDecision:
        return self.security.check_action(
            ActionType.SYSTEM_SETTINGS,
            target=operation,
            payload={"operation": operation, "value": value},
        )

    def execute_set_volume(self, level: int) -> dict:
        pct = max(0, min(100, level))
        if _OS_NAME == "Darwin":
            ok, msg = _run(["osascript", "-e", f"set volume output volume {pct}"])
        elif _OS_NAME == "Linux":
            ok, msg = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"], timeout=3)
        else:
            ok, msg = False, "Volume control not supported on Windows via CLI"
        return {"ok": ok, "message": msg, "volume": pct}

    def execute_set_brightness(self, level: int) -> dict:
        pct = max(0, min(100, level))
        ok, msg = False, "Brightness control not available on this system"
        if _OS_NAME == "Linux":
            ok, msg = _run(["brightnessctl", "set", f"{pct}%"], timeout=3)
        return {"ok": ok, "message": msg, "brightness": pct}

    def execute_media_control(self, action: str) -> dict:
        actions = {"play": "Play", "pause": "Pause", "next": "Next", "prev": "Previous"}
        key = actions.get(action.lower(), action)
        if _OS_NAME == "Darwin":
            ok, msg = _run(["osascript", "-e", f'tell application "Music" to {key.lower()}'])
        else:
            ok, msg = _run(["playerctl", action.lower()], timeout=3)
        return {"ok": ok, "message": msg, "action": action}

    # ---- screenshot

    def request_screenshot(self) -> ActionDecision:
        return self.security.check_action(
            ActionType.SCREEN_CAPTURE,
            target="screen",
            payload={"operation": "screenshot"},
        )

    def execute_screenshot(self, save_path: str = "") -> dict:
        path = save_path or str(Path(tempfile.gettempdir()) / "jarvis_screenshot.png")
        try:
            import pyautogui
            pyautogui.screenshot(path)
            return {"ok": True, "message": f"Screenshot saved to {path}", "path": path}
        except ImportError:
            # Fallback: try platform-specific tools
            if _OS_NAME == "Linux":
                ok, msg = _run(["import", "-window", "root", path])
            elif _OS_NAME == "Darwin":
                ok, msg = _run(["screencapture", path])
            else:
                ok, msg = False, "pyautogui not installed"
            return {"ok": ok, "message": msg, "path": path if ok else ""}

    # ---- clipboard

    def execute_clipboard_copy(self, text: str) -> dict:
        try:
            import pyperclip
            pyperclip.copy(text)
            return {"ok": True, "message": "Copied to clipboard"}
        except ImportError:
            if _OS_NAME == "Linux":
                p = subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True)
                return {"ok": p.returncode == 0, "message": "Copied"}
            return {"ok": False, "message": "Clipboard tool not available"}

    def execute_clipboard_paste(self) -> dict:
        try:
            import pyperclip
            return {"ok": True, "message": pyperclip.paste()}
        except ImportError:
            r = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True)
            return {"ok": r.returncode == 0, "message": r.stdout}

    # ---- system info

    def execute_open_downloads(self) -> dict:
        downloads = str(Path.home() / "Downloads")
        return self.execute_open_website(f"file://{downloads}")

    def execute_open_recycle_bin(self) -> dict:
        if _OS_NAME == "Linux":
            trash = str(Path.home() / ".local/share/Trash/files")
            return self.execute_open_website(f"file://{trash}")
        return {"ok": False, "message": "Not supported on this OS"}

    def execute_open_explorer(self, path: str = "") -> dict:
        target = path or str(Path.home())
        return self.execute_open_website(f"file://{target}")

    # ---- mouse / keyboard (requires pyautogui)

    def click_at(self, x: int, y: int) -> str:
        import pyautogui
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})."

    def type_text(self, text: str) -> str:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        return "Typed."

    def status(self) -> dict:
        return {
            "os": _OS_NAME,
            "platform": platform.platform(),
            "home": str(Path.home()),
            "available_apps": bool(subprocess.run(["which", "xdg-open"], capture_output=True).returncode == 0),
        }
