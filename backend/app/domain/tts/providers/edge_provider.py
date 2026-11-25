"""THE ONLINE KEYLESS TTS PROVIDER (2026-08-30, the user's free-
for-testing pick): the Microsoft Edge neural voices via the
edge-tts CLI (the ~/.local user install) — free, NO key, online.

The voices (Jenny, Aria, Guy, …) are the Edge-browser's neural
voices — genuinely good quality; the synthesis is a simple CLI
call (the subprocess pattern, like the piper). The network's the
only requirement.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from app.domain.tts.interface import TtsVoice

# THE BINARY (2026-08-30): the user-level install (~/.local/bin)
# — the absolute path first (the backend's PATH may not include it).
def _binary() -> str:
    user_bin = Path.home() / ".local" / "bin" / "edge-tts"
    if user_bin.exists():
        return str(user_bin)
    return shutil.which("edge-tts") or "edge-tts"


def _lang(code: str) -> str:
    parts = code.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else "en"


class EdgeProvider:
    name = "edge"
    media_type = "audio/mpeg"

    async def voices(self) -> list[TtsVoice]:
        proc = await asyncio.create_subprocess_exec(
            _binary(), "--list-voices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        voices: list[TtsVoice] = []
        for line in out.decode("utf-8", "replace").splitlines()[2:]:
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            if not name.endswith("Neural"):
                continue
            # the en-* set (the user's language — the picker stays
            # a real choice, not the worldwide clutter)
            if not name.startswith("en-"):
                continue
            voices.append(TtsVoice(name=name, lang=_lang(name), default=False))
        return voices

    async def synthesize(self, text: str, voice: str, rate: float = 1.0) -> bytes:
        # the edge-tts --rate: the percentage ("+10%") — from the rate
        pct = round((rate - 1.0) * 100)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            proc = await asyncio.create_subprocess_exec(
                _binary(),
                "--voice", voice,
                "--text", text,
                "--rate", f"{pct:+d}%",
                "--write-media", str(out_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode != 0:
                # THE USEFUL LINE IS THE LAST ONE. A Python traceback opens with the
                # frame list and ends with the reason; slicing the HEAD left
                # "edge-tts failed (1): Traceback (most recent call last): …" in the
                # log with the actual cause (a 403 from Microsoft's endpoint, a
                # missing voice) cut off past the 200th character.
                detail = err.decode("utf-8", "replace").strip().splitlines()
                reason = " | ".join(line.strip() for line in detail[-3:]) if detail else "no output"
                raise RuntimeError(f"edge-tts failed ({proc.returncode}): {reason[:400]}")
            data = out_path.read_bytes()
            if not data:
                raise RuntimeError("edge-tts produced no audio")
            return data
        finally:
            out_path.unlink(missing_ok=True)
