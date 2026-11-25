"""TTS — the provider-API (thin, 2026-08-30 the provider build).

speak / voices / config — the ONE surface the frontend hits; the
domain routes to the CONFIGURED provider (the piper by default —
the private path; the online is a config flip). The speak returns
the synthesized wav (no-cache — the sounds pattern).

WHICH ENGINE SPEAKS is the `tts` CAPABILITY's answer (phase 5), chosen on `/providers/capabilities` —
never a stored preference. `PUT /config`'s `provider` was the shim that wrote it there
(`set_speech_service`); the shim retired in phase 6 (G2-F4) once the general capability write path
existed, and the field is now REFUSED by the update schema rather than ignored — a stale bundle's
flip must not read as a successful save.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.capabilities import resolve_named_service
from app.domain.tts.config import DEFAULT_CONFIG, get_tts_config, save_tts_config
from app.domain.tts.interface import TtsVoice
from app.domain.tts.registry import get_tts_provider
from app.infrastructure.database import get_db_session

router = APIRouter(prefix="/tts", tags=["tts"])

#: The capability that decides WHICH ENGINE speaks (phase 5 of the service-capability arc). The
#: endpoints below RESOLVE it rather than reading a `provider` off the preferences — one answer, and
#: the same one the providers page shows.
TTS_CAPABILITY = "tts"

TTS_TEXT_MAX = 4000


async def _resolved_engine(db: AsyncSession) -> str | None:
    """The engine the `tts` capability names, or None when nothing is configured."""
    engine, _reason = await resolve_named_service(db, TTS_CAPABILITY)
    return engine


async def _required_engine(db: AsyncSession) -> str:
    """`_resolved_engine`, but an unconfigured capability is a LOUD 503.

    There is no engine name written in code to fall back to — that is the point of the capability.
    """
    engine, reason = await resolve_named_service(db, TTS_CAPABILITY)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No service is configured for the '{TTS_CAPABILITY}' capability "
                f"(reason={reason}) — choose one on the providers page."
            ),
        )
    return engine


class TtsConfigUpdate(BaseModel):
    """The TTS PREFERENCES — and nothing about WHICH engine speaks.

    The engine is the `tts` capability's answer, chosen on `/providers/capabilities`, so this schema
    carries no `provider`; a request still sending one is refused (see the validator) rather than
    ignored.
    """

    voice: str | None = Field(default=None, max_length=100)
    rate: float | None = Field(default=None, ge=0.1, le=4.0)
    enabled: bool | None = None
    source: str | None = Field(default=None, pattern="^(piper|browser)$")
    # THE STICKY MODE (2026-08-31, the TTS P3): the sticky alerts'
    # voice — the siren-loop vs the content read aloud once.
    sticky_mode: str | None = Field(default=None, pattern="^(siren|spoken)$")

    @model_validator(mode="before")
    @classmethod
    def _no_retired_provider(cls, data: Any) -> Any:
        """Refuse a request still carrying `provider` — LOUDLY, naming the replacement.

        The engine moved onto the `tts` capability row in phase 5 (as the shim `set_speech_service`)
        and the shim retired here (phase 6, G2-F4) now that the general capability write path exists.
        A request still setting `provider` is therefore a producer that has not moved — and an ignored
        key is the worse option: the save would SUCCEED while the value went nowhere, which is
        indistinguishable from a working engine flip.

        REMOVAL CONDITION: delete this guard once no producer can send the shape — the speech page no
        longer sends it **and** no built frontend bundle still in use does. A TRANSITION guard.
        """
        if isinstance(data, dict) and "provider" in data:
            raise ValueError(
                "`provider` is retired: which engine speaks is the `tts` capability's answer. "
                "Remove the field from the request, and change the engine at "
                "/providers/capabilities — this endpoint carries the preferences only "
                "(voice, rate, enabled, sticky_mode)."
            )
        return data


def _default_voice(voices: list[TtsVoice]) -> str | None:
    """The voice a FRESH choice on this engine should be: the app's configured voice when the engine
    offers it, else the engine's first.

    ONE home for the rule the engine-flip used to carry (it re-picked the voice on every flip, because
    a voice from the old engine errors on the new one). The flip now happens on
    `/providers/capabilities`, where nothing knows about voices — so the rule is published HERE, with
    the list, and whoever repairs a stale voice preference applies it.
    """
    names = [v["name"] for v in voices]
    if not names:
        return None
    return DEFAULT_CONFIG["voice"] if DEFAULT_CONFIG["voice"] in names else names[0]


async def _require_enabled(db: AsyncSession) -> dict:
    """THE OFF SWITCH IS A SWITCH, NOT A HINT (2026-11-25).

    `enabled` gated the frontend, and a frontend gate is not a control: a stale tab,
    a script or a plain curl could still ask this endpoint to speak — and speaking is
    an OUTBOUND call to a third party (the keyless edge-tts path talks to Microsoft).
    Spurious network access is a security problem, not a UX preference, so a disabled
    install refuses HERE: before the engine is resolved, before a provider is built,
    before any subprocess or socket is opened.
    """
    cfg = await get_tts_config(db)
    if not cfg.get("enabled", False):
        raise HTTPException(
            status_code=409,
            detail="Speech is switched off. Turn it on in Speech settings.",
        )
    return cfg


@router.get("/voices")
async def list_voices(db: AsyncSession = Depends(get_db_session)):
    """The configured provider's selectable voices, and which of them a fresh choice should be.

    `default` exists so a client can reconcile a voice preference that no longer belongs to the
    engine — the engine can be changed elsewhere now, and a stale voice would otherwise error on the
    next speak ("Unknown piper voice: …").
    """
    await _require_enabled(db)
    try:
        provider = get_tts_provider(await _required_engine(db))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    voices = await provider.voices()
    return {"provider": provider.name, "voices": voices, "default": _default_voice(voices)}


@router.get("/speak")
async def speak(
    text: str = Query(..., min_length=1, max_length=TTS_TEXT_MAX),
    voice: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Synthesize the text -> the wav bytes (the configured provider)."""
    cfg = await _require_enabled(db)
    try:
        provider = get_tts_provider(await _required_engine(db))
        wav = await provider.synthesize(text, voice or cfg["voice"], rate=cfg.get("rate", 1.0))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(
        content=wav,
        media_type=getattr(provider, "media_type", "audio/wav"),
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/config")
async def read_config(db: AsyncSession = Depends(get_db_session)):
    """The preferences PLUS the engine the capability names — what the page renders."""
    return {**(await get_tts_config(db)), "provider": await _resolved_engine(db)}


@router.put("/config")
async def update_config(
    update: TtsConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update the TTS PREFERENCES. WHICH engine speaks is not here — it is the capability's answer.

    A request still carrying `provider` never reaches this handler: the schema refuses it, naming
    `/providers/capabilities` (see ``TtsConfigUpdate``). The engine used to be flipped here, and the
    flip re-picked the voice for the new engine; both moved out with the shim — the voice repair now
    lives with the voice list (`GET /voices`'s `default`), because the engine changes where nothing
    knows about voices.
    """
    updates = update.model_dump(exclude_unset=True)

    if update.voice is not None:
        # the voice must belong to the engine that will speak it
        try:
            provider = get_tts_provider(await _required_engine(db))
            known = {v["name"] for v in await provider.voices()}
            if update.voice not in known:
                raise HTTPException(status_code=400, detail=f"Unknown voice: {update.voice}")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    cfg = await save_tts_config(db, updates)
    return {**cfg, "provider": await _resolved_engine(db)}
