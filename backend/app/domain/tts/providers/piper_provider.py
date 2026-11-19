"""THE PRIVATE TTS PROVIDER (2026-08-30, the provider build).

The local piper engine: the standalone binary + the onnx voice
models in backend/data/piper/ (the runtime, gitignored — per-machine
by design). No keys, no network — the synthesis stays on the
machine. The provider spawns the binary per request (the subprocess
pattern) and returns the wav bytes.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.core.config import Paths, get_settings
from app.domain.tts.interface import TtsVoice


class PiperProvider:
    name = "piper"
    media_type = "audio/wav"

    def _piper_dir(self) -> Path:
        return Paths.from_settings(get_settings()).piper_dir

    async def voices(self) -> list[TtsVoice]:
        d = self._piper_dir()
        if not d.exists():
            return []
        return [
            {"name": p.name[:-5], "lang": "en-US", "default": False}
            for p in sorted(d.glob("*.onnx"))
        ]

    async def synthesize(self, text: str, voice: str, rate: float = 1.0) -> bytes:
        model = self._piper_dir() / f"{voice}.onnx"
        if not model.exists():
            raise ValueError(f"Unknown piper voice: {voice}")
        binary = self._piper_dir() / "piper"
        if not binary.exists():
            raise RuntimeError("The piper binary is missing (backend/data/piper/)")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            # piper's --length_scale: >1 slower, <1 faster — 1/rate
            length_scale = str(max(0.1, 1.0 / rate))
            proc = await asyncio.create_subprocess_exec(
                str(binary),
                "--model", str(model),
                "--output_file", str(out_path),
                "--length_scale", length_scale,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate(text.encode("utf-8"))
            if proc.returncode != 0:
                raise RuntimeError(f"piper failed ({proc.returncode})")
            data = out_path.read_bytes()
            if not data:
                raise RuntimeError("piper produced no audio")
            return data
        finally:
            out_path.unlink(missing_ok=True)
