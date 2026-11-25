"""The TTS configuration — the UserSettings-backed store.

The TTS PREFERENCES live in the UserSettings JSON blob under the
"tts" key (the notifications-config pattern). Shape:

    {"voice": "en_US-lessac-medium", "rate": 1.0,
     "enabled": false, "source": "piper", "sticky_mode": "siren"}

- voice: the engine's voice name (the piper model's filename stem).
- rate: the speaking speed (1.0 = normal).
- enabled: the global TTS on/off (the P2 toggle). **OFF out of the box** —
  shipping it on made a fresh install read every reply aloud and, where TTS is
  unconfigured, raise a failure notice nobody asked for.
- source: the voice SOURCE — "piper" (the app's TTS API) vs
  "browser" (the system's speechSynthesis — the OS voice, no API).
  The user's switch ask (2026-08-30). This is a PATH preference, not
  an engine: the live blob carries `source: "piper"` beside an engine
  of `edge`, which is how the two are known to be independent.
- sticky_mode: the sticky-alerts' voice mode (the TTS P3,
  2026-08-31) — "siren" (the wav-loop, the default) vs "spoken"
  (the alert's content read aloud once by the TTS).

**THE ENGINE IS NOT HERE** (phase 5 of the service-capability arc):
which engine speaks is the `tts` CAPABILITY's answer
(`app.domain.providers.capabilities.resolve`) — the same one the
providers page shows and edits. `provider` is refused on write and
stripped on read, so a blob that still carries the retired key cannot
read as a second answer to a question the capability owns.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import UserSettings

CONFIG_KEY = "tts"

#: The retired key: the engine. Stripped on read, refused on write — named so the strip is not a
#: mystery, and so a stale blob value cannot reappear through a merge.
RETIRED_KEYS: tuple[str, ...] = ("provider",)

DEFAULT_CONFIG: dict = {
    "voice": "en_US-lessac-medium",
    "rate": 1.0,
    # THE SHIPPED STATE IS OFF (2026-11-25, the user's ruling). Speech is an OUTBOUND
    # call to a third party — the keyless edge-tts path talks to Microsoft, and the
    # piper path has to be installed per machine — so a fresh install must not start
    # speaking on its own: no auto-read, no failure notice nobody asked for, no traffic
    # to a service nobody chose. Turning it on is one deliberate press on /speech.
    "enabled": False,
    "source": "piper",
    "sticky_mode": "siren",
}


async def get_tts_config(db: AsyncSession) -> dict:
    """Load the persisted TTS preferences (or the defaults)."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_key == "default")
    )
    row = result.scalar_one_or_none()
    if row is None or not row.settings:
        return dict(DEFAULT_CONFIG)
    cfg = {**DEFAULT_CONFIG, **row.settings.get(CONFIG_KEY, {})}
    for key in RETIRED_KEYS:
        cfg.pop(key, None)
    return cfg


async def save_tts_config(db: AsyncSession, updates: dict) -> dict:
    """Merge + persist the TTS preferences; return the new state.

    A retired key in `updates` is DROPPED rather than stored: the engine has one home now, and a
    second copy is exactly what this arc removed.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_key == "default")
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UserSettings(user_key="default", settings={})
        db.add(row)
        await db.flush()
    current = row.settings.get(CONFIG_KEY, {}) if row.settings else {}
    merged = {
        **DEFAULT_CONFIG,
        **current,
        **{k: v for k, v in updates.items() if v is not None and k not in RETIRED_KEYS},
    }
    row.settings = {**(row.settings or {}), CONFIG_KEY: merged}
    await db.commit()
    return dict({k: v for k, v in merged.items() if k not in RETIRED_KEYS})
