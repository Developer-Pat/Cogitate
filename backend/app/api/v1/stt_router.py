"""STT — the provider-API (thin, 2026-08-30 the _26 build — the TTS
mirror).

transcribe / config — the ONE surface the frontend hits; the
domain routes to the CONFIGURED provider (the whisper — the local
keyless). The ROUND-TRIP harness's ear: the TTS speaks -> the wav
-> this endpoint hears it -> the text.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.capabilities import resolve_named_service
from app.domain.stt.config import get_stt_config, save_stt_config
from app.domain.stt.registry import get_stt_provider
from app.infrastructure.database import get_db_session

router = APIRouter(prefix="/stt", tags=["stt"])

#: The capability that decides WHICH ENGINE transcribes (phase 5 of the service-capability arc).
#: The endpoints below RESOLVE it rather than reading a `provider` off the preferences — one answer,
#: and the same one the providers page shows.
STT_CAPABILITY = "stt"

# THE AUDIO CAP (2026-08-30): the round-trip wavs are a few
# hundred KB; the cap bounds the uploads (the house's 422-guard).
AUDIO_MAX_BYTES = 25 * 1024 * 1024


async def _resolved_engine(db: AsyncSession) -> str | None:
    """The engine the `stt` capability names, or None when nothing is configured."""
    engine, _reason = await resolve_named_service(db, STT_CAPABILITY)
    return engine


async def _required_engine(db: AsyncSession) -> str:
    """`_resolved_engine`, but an unconfigured capability is a LOUD 503.

    There is no engine name written in code to fall back to — that is the point of the capability.
    """
    engine, reason = await resolve_named_service(db, STT_CAPABILITY)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No service is configured for the '{STT_CAPABILITY}' capability "
                f"(reason={reason}) — choose one on the providers page."
            ),
        )
    return engine


class SttConfigUpdate(BaseModel):
    """The STT PREFERENCES — and nothing about WHICH engine transcribes.

    The engine is the `stt` capability's answer, chosen on `/providers/capabilities`; a request still
    sending `provider` is refused (see the validator) rather than ignored.
    """

    enabled: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_retired_provider(cls, data: Any) -> Any:
        """Refuse a request still carrying `provider` — LOUDLY, naming the replacement.

        The same retirement as the TTS mirror (`tts_router.TtsConfigUpdate`): the engine moved onto
        the `stt` capability row in phase 5 (as the shim `set_speech_service`) and the shim retired
        here (phase 6, G2-F4) now that the general capability write path exists. An ignored key would
        make the save SUCCEED while the value went nowhere — indistinguishable from a working flip.

        REMOVAL CONDITION: delete this guard once no producer can send the shape — nothing in the app
        sends it (**the speech page never had an STT engine switch**, only an enable toggle) **and**
        no built frontend bundle still in use does. A TRANSITION guard.
        """
        if isinstance(data, dict) and "provider" in data:
            raise ValueError(
                "`provider` is retired: which engine transcribes is the `stt` capability's answer. "
                "Remove the field from the request, and change the engine at "
                "/providers/capabilities — this endpoint carries the enabled preference only."
            )
        return data


@router.post("/transcribe")
async def transcribe(
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
):
    """Transcribe the uploaded audio (wav/mp3) -> the text."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The audio is empty")
    if len(data) > AUDIO_MAX_BYTES:
        raise HTTPException(
            status_code=422, detail=f"The audio exceeds {AUDIO_MAX_BYTES} bytes"
        )
    cfg = await get_stt_config(db)
    if not cfg.get("enabled", True):
        raise HTTPException(status_code=400, detail="STT is disabled")
    try:
        provider = get_stt_provider(await _required_engine(db))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        result = await provider.transcribe(data)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"provider": provider.name, **result}


@router.get("/config")
async def read_config(db: AsyncSession = Depends(get_db_session)):
    """The preferences PLUS the engine the capability names — what the page renders."""
    return {**(await get_stt_config(db)), "provider": await _resolved_engine(db)}


@router.put("/config")
async def update_config(
    update: SttConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update the STT PREFERENCES. WHICH engine transcribes is the capability's answer, not a field.

    A request still carrying `provider` never reaches this handler — the schema refuses it, naming
    `/providers/capabilities` (see ``SttConfigUpdate``).
    """
    updates = update.model_dump(exclude_unset=True)
    cfg = await save_stt_config(db, updates)
    return {**cfg, "provider": await _resolved_engine(db)}
