"""Notifications configuration — the UserSettings-backed store.

The notification preferences live in the UserSettings JSON blob under
the "notifications" key (the same pattern as the external-agent
config). Shape:

    {"suppressed": bool, "audio_enabled": bool, "sound_id": str,
     "mute_until": float | None, "volume": float,
     "sound_success": str, "sound_warning": str, "sound_error": str,
     "sound_level": str}

- suppressed: the airplane-mode flag — the toasts are muted (the
  display only) while the messages keep flowing to the message center
  (the queue + the counts persist). The UI: the Sounds page's mute
  row (2026-08-29, the notifications-upgrade).
- audio_enabled: play the selected sound when an attention-worthy
  toast fires (the audio-ping option — off by default).
- sound_id: the notification sound's filename in the sounds store.
- mute_until: the scheduled-mute's end (epoch seconds) — the
  APScheduler job restores suppressed=false + announces at expiry;
  the startup heal covers a missed job (a mute that expired during
  downtime).
- volume: the audio-ping's loudness (0.0-1.0, the HTMLAudio volume;
  1.0 = the synthesized level — the default keeps the current
  behavior).
- sound_success / sound_warning / sound_error: THE PER-CLASS SOUNDS
  (2026-08-30, the F4 design): the class-specific wavs — the
  container plays the class's sound (success -> the run-complete
  bell, warning -> the alert, error -> the emergency); sound_id is
  the fallback. Defaults: end-of-run.wav / alert.wav / emergency.wav.
- sound_level: THE SOUND LEVEL (2026-08-30, the user's ask): the
  MINIMUM class that pings — "warning" by default (the alerts + the
  emergencies; the run-complete bell is silent below the level). The
  ranks: info < success < warning < error.

The backend validates sound_id against the store on write; the delete
guard on the sounds router refuses to remove the configured sound.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import UserSettings

CONFIG_KEY = "notifications"

DEFAULT_CONFIG: dict = {
    "suppressed": False,
    "audio_enabled": False,
    "sound_id": "gentle-ping.wav",
    "mute_until": None,
    "volume": 1.0,
    "sound_success": "end-of-run.wav",
    "sound_warning": "alert.wav",
    "sound_error": "emergency.wav",
    "sound_level": "warning",
}


async def get_notifications_config(db: AsyncSession) -> dict:
    """Load the persisted notifications config (or the defaults)."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_key == "default")
    )
    row = result.scalars().first()
    if row is None:
        return dict(DEFAULT_CONFIG)
    blob = row.settings or {}
    saved = blob.get(CONFIG_KEY)
    if not isinstance(saved, dict):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in saved.items() if k in merged})
    return merged


async def save_notifications_config(
    db: AsyncSession, update: dict, clear: set[str] | None = None
) -> dict:
    """Merge + persist the config (additive — never drops unknown keys).

    clear: keys to REMOVE (the mute_until's cancellation — a None
    value alone would be skipped by the merge's None-guard).
    """
    current = await get_notifications_config(db)
    current.update(
        {k: v for k, v in update.items() if k in current and v is not None}
    )
    for key in clear or set():
        current.pop(key, None)

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_key == "default")
    )
    row = result.scalars().first()
    if row is None:
        row = UserSettings(user_key="default", settings={})
        db.add(row)
    blob = dict(row.settings or {})
    blob[CONFIG_KEY] = current
    row.settings = blob
    await db.commit()
    return current
