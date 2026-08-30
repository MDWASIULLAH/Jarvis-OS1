"""
capabilities/voice_pipeline.py

Reference integration for local, offline STT/TTS (Section 2.1 / 10.2):
- transcribe() uses faster-whisper (CPU-friendly Whisper reimplementation)
- speak() shells out to Piper's CLI for offline text-to-speech

Honest note, and this is the important one: this needs a real microphone
and speaker on a real machine to mean anything. This sandbox has neither --
there is no audio hardware here, so "5 stars, verified" isn't something
that can honestly be claimed for voice from inside a chat conversation, no
matter how much code gets written. What follows is correct, standard
integration code for when you run this on your own computer:

    pip install faster-whisper
    # download a Piper voice, e.g. en_US-lessac-medium, from
    # https://github.com/rhasspy/piper/releases

Wake-word detection ("Hey JARVIS") is a further, separate piece on top of
this -- a lightweight always-listening keyword spotter (openWakeWord and
Porcupine are the common free/open options) that triggers transcribe()
only when it hears the wake word, so the mic isn't being fully processed
(or sent anywhere) all the time. Not included here, same reasoning as
above: no mic to test it against.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def transcribe(audio_path: str, model_size: str = "base") -> str:
    """Requires `pip install faster-whisper`. Import is deferred so this
    module doesn't hard-fail for people who haven't installed it yet."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path)
    return " ".join(segment.text.strip() for segment in segments).strip()


def speak(text: str, piper_voice_path: str, output_path: str = "/tmp/jarvis_speech.wav") -> Optional[str]:
    """Requires the `piper` binary on PATH and a downloaded .onnx voice file."""
    try:
        proc = subprocess.run(
            ["piper", "--model", piper_voice_path, "--output_file", output_path],
            input=text,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return None
        return output_path if Path(output_path).exists() else None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
