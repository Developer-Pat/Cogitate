"""The STT configuration — the UserSettings-backed store (the TTS
pattern mirrored). The preferences live under the "stt" key:

    {"enabled": true}

- enabled: the global STT on/off (the P4 surface's toggle).

**THE ENGINE IS NOT HERE** (phase 5 of the service-capability arc):
which engine transcribes is the `stt` CAPABILITY's answer
(`app.domain.providers.capabilities.resolve`), the same one the
providers page shows and edits. This store holds what belongs to the
USER, and `provider` is refused on write and stripped on read — so a
blob that still carries the retired key cannot read as a second
answer to a question the capability owns.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import UserSettings

CONFIG_KEY = "stt"

#: The retired key: the engine. Stripped on read, refused on write — named so the strip is not a
#: mystery, and so a stale blob value cannot reappear through a merge.
RETIRED_KEYS: tuple[str, ...] = ("provider",)

DEFAULT_CONFIG: dict = {
    "enabled": True,
}


async def get_stt_config(db: AsyncSession) -> dict:
    """Load the persisted STT preferences (or the defaults)."""
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


async def save_stt_config(db: AsyncSession, updates: dict) -> dict:
    """Merge + persist the STT preferences; return the new state.

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
