"""Voice input for Aish — record mic audio, transcribe with whisper.cpp.

Usage:
  aish --listen         # One-shot: listen → transcribe → run
  In shell: /listen    # Toggle listen mode

Requires: whisper.cpp built at ~/whisper.cpp/
Model: ~/models/whisper/ggml-tiny.en-q5_0.bin (28 MB)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

WHISPER_DIR = Path.home() / "whisper.cpp"
WHISPER_CLI = WHISPER_DIR / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = Path.home() / "models" / "whisper" / "ggml-tiny.en-q5_0.bin"


def available() -> bool:
    """Check if whisper.cpp and model are available."""
    return WHISPER_CLI.exists() and WHISPER_MODEL.exists()


def record_audio(duration: int = 5, sample_rate: int = 16000) -> Optional[str]:
    """Record audio from microphone using arecord.

    Returns path to WAV file, or None if recording fails.
    """
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="aish_")
    os.close(fd)

    try:
        result = subprocess.run(
            ["arecord", "-d", str(duration), "-f", "S16_LE",
             "-r", str(sample_rate), "-c", "1", "-t", "wav", path],
            capture_output=True, text=True, timeout=duration + 5,
        )
        if result.returncode != 0:
            print(f"  [voice] Recording failed: {result.stderr.strip()}")
            os.unlink(path)
            return None
        return path
    except subprocess.TimeoutExpired:
        os.unlink(path)
        return None
    except FileNotFoundError:
        print("  [voice] arecord not found. Install: sudo dnf install alsa-utils")
        os.unlink(path)
        return None


def transcribe(audio_path: str) -> Optional[str]:
    """Transcribe audio file using whisper.cpp.

    Returns transcribed text, or None on failure.
    """
    try:
        result = subprocess.run(
            [str(WHISPER_CLI), "-m", str(WHISPER_MODEL),
             "-f", audio_path, "-otxt"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"  [voice] Transcription failed: {result.stderr.strip()[:100]}")
            return None

        # Read the output file created by -otxt
        txt_path = audio_path + ".txt"
        if os.path.exists(txt_path):
            text = Path(txt_path).read_text().strip()
            # Remove timestamps like [00:00:00.000 --> ...]
            import re
            lines = re.sub(r'\[\d+:\d+:\d+\.\d+ --> \d+:\d+:\d+\.\d+\]\s*', '', text)
            lines = lines.strip()
            if lines and lines != "[BLANK_AUDIO]":
                return lines
            return None

        # Fallback: parse stdout
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line and not line.startswith("[") and len(line) > 5:
                return line
        return None

    except subprocess.TimeoutExpired:
        print("  [voice] Transcription timed out")
        return None
    except FileNotFoundError:
        print(f"  [voice] whisper-cli not found at {WHISPER_CLI}")
        return None


def listen_and_transcribe(duration: int = 5) -> Optional[str]:
    """Full pipeline: record → transcribe → return text.

    Uses voice activity detection when available.
    """
    if not available():
        print("  [voice] whisper.cpp or model not found.")
        print(f"  Install: cd ~&& git clone https://github.com/ggerganov/whisper.cpp")
        print(f"           cd whisper.cpp && cmake -B build && cmake --build build -j")
        print(f"  Model: hf download Pomni/whisper-tiny.en-ggml-allquants --local-dir ~/models/whisper")
        return None

    print(f"  [voice] Listening for {duration}s... (speak now)")
    audio_path = record_audio(duration)
    if not audio_path:
        return None

    try:
        text = transcribe(audio_path)
        if text:
            return text
        print("  [voice] No speech detected")
        return None
    finally:
        if audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)
        # Also clean up the .txt output file
        txt_path = audio_path + ".txt"
        if txt_path and os.path.exists(txt_path):
            os.unlink(txt_path)
