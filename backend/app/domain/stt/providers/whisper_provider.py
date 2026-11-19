"""THE WHISPER PROVIDER (2026-08-30, the _26 build): the local,
keyless, offline STT via faster-whisper (the CTranslate2 whisper).
The piper-analog: a self-hosted model, no keys, no network at
transcribe time (the model downloads once on the first use).

THE SUBPROCESS BRIDGE (the 3.12-gap lesson): the backend's venv is
Python 3.14 — no faster-whisper wheels — so the provider shells
out to the system python3's transcribe.py (the edge-tts pattern:
the runtime lives OUTSIDE the venv, the provider is the bridge).

THE ROUND-TRIP HARNESS: this is the ear that hears the piper's
mouth — the deterministic TTS->STT accuracy test's second half.
"""

import asyncio
import json
import subprocess

from app.domain.stt.interface import SttResult

# THE SYSTEM-SIDE SCRIPT (the runtime home — the piper pattern):
# <root>/backend/data/stt/transcribe.py — run by the SYSTEM python3
# (3.12, where the user-site faster-whisper lives).
#
# Located from the RESOLVER's root, not by counting parents from __file__:
# a parent-crawl silently survives a refactor that moves this file, and lands
# somewhere else entirely (the phantom-path class). Rooted at the installation,
# so a redirected or packaged install resolves it correctly.
from app.core.config import Paths as _Paths, get_settings as _get_settings

_TRANSCRIBE_SCRIPT = (
    _Paths.from_settings(_get_settings()).root / "backend" / "data" / "stt" / "transcribe.py"
)


class WhisperProvider:
    name = "whisper"

    async def transcribe(self, audio: bytes) -> SttResult:
        def _run() -> SttResult:
            # THE BRIDGE: the system python3 reads the audio from
            # the stdin, prints the JSON — the offload's implicit
            # (the subprocess runs outside the event loop).
            proc = subprocess.run(
                ["python3", str(_TRANSCRIBE_SCRIPT)],
                input=audio,
                capture_output=True,
                timeout=300,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"whisper transcribe failed: {proc.stderr.decode()[-300:]}"
                )
            data = json.loads(proc.stdout.decode())
            if "error" in data:
                raise RuntimeError(f"whisper error: {data['error']}")
            return SttResult(
                text=data["text"],
                language=data["language"],
                duration=data["duration"],
            )

        return await asyncio.to_thread(_run)
