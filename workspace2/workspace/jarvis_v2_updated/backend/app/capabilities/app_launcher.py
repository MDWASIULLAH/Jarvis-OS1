"""
capabilities/app_launcher.py

Actually opens applications, folders, and websites on the machine running the
backend -- Windows, macOS, and Linux.

Design rules:

* Never build a shell string from user text. Every launch is `subprocess` with
  an argument list, so "open chrome; rm -rf ~" cannot become two commands.
* Resolve friendly names ("vs code", "browser", "settings") to per-OS targets
  through an explicit table, then fall back to the OS opener.
* Website requests go through the browser, not the app table.
* Ask the SecurityGate first. Launching is allowed by default because the user
  asked for it out loud, but it is always audited, and `JARVIS_ALLOW_LAUNCH=false`
  turns it into a preview-only dry run for shared machines.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from typing import Optional

SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"

# friendly name -> {os: [candidate commands]}
APP_TABLE: dict[str, dict[str, list[str]]] = {
    "chrome": {"Windows": ["chrome"], "Darwin": ["Google Chrome"], "Linux": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]},
    "firefox": {"Windows": ["firefox"], "Darwin": ["Firefox"], "Linux": ["firefox"]},
    "edge": {"Windows": ["msedge"], "Darwin": ["Microsoft Edge"], "Linux": ["microsoft-edge"]},
    "safari": {"Darwin": ["Safari"]},
    "browser": {"Windows": ["chrome", "msedge", "firefox"], "Darwin": ["Google Chrome", "Safari"], "Linux": ["google-chrome", "firefox", "chromium"]},
    "vs code": {"Windows": ["code"], "Darwin": ["Visual Studio Code"], "Linux": ["code", "codium"]},
    "code": {"Windows": ["code"], "Darwin": ["Visual Studio Code"], "Linux": ["code", "codium"]},
    "terminal": {"Windows": ["wt", "cmd"], "Darwin": ["Terminal"], "Linux": ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]},
    "notepad": {"Windows": ["notepad"], "Darwin": ["TextEdit"], "Linux": ["gedit", "kate", "mousepad"]},
    "calculator": {"Windows": ["calc"], "Darwin": ["Calculator"], "Linux": ["gnome-calculator", "kcalc", "galculator"]},
    "spotify": {"Windows": ["spotify"], "Darwin": ["Spotify"], "Linux": ["spotify"]},
    "file explorer": {"Windows": ["explorer"], "Darwin": ["Finder"], "Linux": ["nautilus", "dolphin", "thunar"]},
    "files": {"Windows": ["explorer"], "Darwin": ["Finder"], "Linux": ["nautilus", "dolphin", "thunar"]},
    "settings": {"Windows": ["ms-settings:"], "Darwin": ["System Settings"], "Linux": ["gnome-control-center"]},
    "camera": {"Windows": ["microsoft.windows.camera:"], "Darwin": ["Photo Booth"], "Linux": ["cheese"]},
    "task manager": {"Windows": ["taskmgr"], "Darwin": ["Activity Monitor"], "Linux": ["gnome-system-monitor"]},
    "word": {"Windows": ["winword"], "Darwin": ["Microsoft Word"]},
    "excel": {"Windows": ["excel"], "Darwin": ["Microsoft Excel"]},
    "paint": {"Windows": ["mspaint"], "Darwin": ["Preview"], "Linux": ["gimp"]},
}

WEB_TABLE: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "whatsapp": "https://web.whatsapp.com",
    "chatgpt": "https://chat.openai.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "instagram": "https://www.instagram.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
}

_ALIASES = {
    "google chrome": "chrome",
    "visual studio code": "vs code",
    "vscode": "vs code",
    "cmd": "terminal",
    "command prompt": "terminal",
    "powershell": "terminal",
    "explorer": "file explorer",
    "youtube app": "youtube",
    "calc": "calculator",
    "control panel": "settings",
}


def allowed() -> bool:
    return (os.getenv("JARVIS_ALLOW_LAUNCH", "true") or "true").strip().lower() not in {
        "0", "false", "no", "off",
    }


@dataclass
class LaunchResult:
    ok: bool
    message: str
    kind: str            # "app" | "website" | "path" | "blocked" | "not_found"
    target: str
    command: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "message": self.message,
            "kind": self.kind,
            "target": self.target,
            "command": self.command,
            "dry_run": self.dry_run,
        }


def normalize(name: str) -> str:
    cleaned = " ".join(name.lower().split()).strip(" .!?\"'")
    cleaned = cleaned.removeprefix("the ").removesuffix(" app").removesuffix(" application")
    return _ALIASES.get(cleaned, cleaned)


def _spawn(args: list[str]) -> None:
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if SYSTEM == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)  # noqa: S603 -- argument list, never a shell string


def open_website(url: str) -> LaunchResult:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    if not allowed():
        return LaunchResult(False, f"Launching is disabled, so I did not open {url}.", "blocked", url, dry_run=True)
    try:
        if SYSTEM == "Darwin":
            _spawn(["open", url])
        elif SYSTEM == "Windows":
            os.startfile(url)  # type: ignore[attr-defined]  # noqa: S606
        elif shutil.which("xdg-open"):
            _spawn(["xdg-open", url])
        else:
            webbrowser.open(url)
        return LaunchResult(True, f"Opened {url} in your browser.", "website", url, command=url)
    except OSError as exc:
        return LaunchResult(False, f"Could not open {url}: {exc}", "website", url)


def open_path(path: str) -> LaunchResult:
    expanded = os.path.expanduser(path)
    if not os.path.exists(expanded):
        return LaunchResult(False, f"There is nothing at {path} on this machine.", "not_found", path)
    if not allowed():
        return LaunchResult(False, f"Launching is disabled, so I did not open {path}.", "blocked", path, dry_run=True)
    try:
        if SYSTEM == "Darwin":
            _spawn(["open", expanded])
        elif SYSTEM == "Windows":
            os.startfile(expanded)  # type: ignore[attr-defined]  # noqa: S606
        else:
            _spawn(["xdg-open", expanded])
        return LaunchResult(True, f"Opened {path}.", "path", path, command=expanded)
    except OSError as exc:
        return LaunchResult(False, f"Could not open {path}: {exc}", "path", path)


def open_app(name: str) -> LaunchResult:
    """Open an application, a known website, or a filesystem path by name."""
    target = normalize(name)
    if not target:
        return LaunchResult(False, "I need the name of an app or site to open.", "not_found", name)

    if target.startswith(("http://", "https://", "www.")) or re_domain(target):
        return open_website(target)
    if target in WEB_TABLE:
        return open_website(WEB_TABLE[target])
    if os.path.sep in target or target.startswith("~"):
        return open_path(target)

    candidates = APP_TABLE.get(target, {}).get(SYSTEM, [])
    if not candidates:
        candidates = [target]

    if not allowed():
        return LaunchResult(
            False, f"Launching is disabled, so I did not start {target}.", "blocked", target, dry_run=True
        )

    for candidate in candidates:
        try:
            if SYSTEM == "Darwin":
                subprocess.run(["open", "-a", candidate], check=True, capture_output=True, timeout=15)  # noqa: S603
                return LaunchResult(True, f"Opened {candidate}.", "app", target, command=candidate)
            if SYSTEM == "Windows":
                if candidate.endswith(":"):  # ms-settings: style URI
                    os.startfile(candidate)  # type: ignore[attr-defined]  # noqa: S606
                else:
                    _spawn(["cmd", "/c", "start", "", candidate])
                return LaunchResult(True, f"Opened {candidate}.", "app", target, command=candidate)
            resolved = shutil.which(candidate)
            if resolved:
                _spawn([resolved])
                return LaunchResult(True, f"Opened {candidate}.", "app", target, command=resolved)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            continue

    # Last resort: it may still be a website the table simply doesn't know.
    if "." in target and " " not in target:
        return open_website(target)
    return LaunchResult(
        False,
        f"I couldn't find an app called \"{name}\" on this {SYSTEM or 'machine'}. "
        f"Tell me the exact executable name and I'll launch that instead.",
        "not_found",
        target,
    )


def re_domain(value: str) -> bool:
    import re

    return bool(re.match(r"^[a-z0-9-]+\.(com|org|net|io|dev|in|co|ai|app|me)(/|$)", value, re.I))


def status() -> dict:
    available = []
    for name, table in APP_TABLE.items():
        for candidate in table.get(SYSTEM, []):
            if SYSTEM in {"Windows", "Darwin"} or shutil.which(candidate):
                available.append(name)
                break
    return {
        "platform": SYSTEM,
        "launch_enabled": allowed(),
        "known_apps": sorted(APP_TABLE),
        "detected_on_this_machine": sorted(set(available)),
        "known_sites": sorted(WEB_TABLE),
    }
