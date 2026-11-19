"""Notifications configuration — API (thin, 2026-08-30 the F2
extraction).

GET/PUT /api/v1/notifications/config — the notification preferences
(suppressed + audio_enabled + sound_id + mute_until + volume),
backed by the UserSettings blob (see
domain/messaging/notifications_config.py). The SCHEDULING (the mute
restore job + the startup heal) lives in
domain/messaging/notifications.py — this router stays thin.
"""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.domain.messaging import notifications, sounds
from app.domain.messaging.notifications_config import (
    get_notifications_config,
    save_notifications_config,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _db():
    from app.infrastructure.database import get_db_session
    async for session in get_db_session():
        yield session


class NotificationsConfigUpdate(BaseModel):
    suppressed: bool | None = None
    audio_enabled: bool | None = None
    sound_id: str | None = Field(default=None, max_length=255)
    mute_until: float | None = None
    volume: float | None = Field(default=None, ge=0.0, le=1.0)
    sound_success: str | None = Field(default=None, max_length=255)
    sound_warning: str | None = Field(default=None, max_length=255)
    sound_error: str | None = Field(default=None, max_length=255)


class NotificationsTestPayload(BaseModel):
    """The notification-test payload (2026-08-30, the user's test
    ask): publish a notify event through the real bus — the SSE
    delivers it to EVERY open tab (the per-tab stream delivery)."""
    title: str = Field(min_length=1, max_length=200)
    message: str = ""
    type: str = Field(default="info", pattern="^(info|success|warning|error)$")
    sticky: bool = False
    from_: str | None = Field(default=None, alias="from")
    link: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=100)


@router.get("/config")
async def get_config(db=Depends(_db)):
    """The current notification preferences."""
    return await get_notifications_config(db)


@router.post("/test")
async def test_notification(payload: NotificationsTestPayload):
    """THE TEST ENDPOINT (2026-08-30): publish a notify event through
    the real bus — the SSE carries it to every open tab; the bridge
    toasts it (the sticky flag included). The test affordance for the
    notification chain (the user's test-culture)."""
    from app.domain.messaging.services import publish

    body: dict = {
        "title": payload.title,
        "message": payload.message,
        "type": payload.type,
        "from": payload.from_ or "system",
        "kind": "notifications-test",
        "sticky": payload.sticky,
    }
    if payload.link:
        from app.domain.tools.builtin.send_notification_handler import _safe_link

        if not _safe_link(payload.link):
            raise HTTPException(status_code=400, detail="link must be an app route (/...) or an http(s) URL")
        body["action"] = {
            "label": payload.link_label or "Open",
            "href": payload.link,
        }
    publish("notify:test", body)
    return {
        "ok": True,
        "title": payload.title,
        "type": payload.type,
        "sticky": payload.sticky,
        "link": payload.link,
    }


@router.put("/config")
async def update_config(update: NotificationsConfigUpdate, db=Depends(_db)):
    """Merge the notification preferences. sound_id is validated
    against the sounds store (a nonexistent sound is a 400 — no
    silent mute)."""
    # the sound fields validate against the store (a nonexistent
    # sound is a 400 — no silent mute; the per-class fields included).
    # THE PER-CLASS NONE (2026-08-31, the user's null-wav ask): the
    # EMPTY string is the per-class SILENT — the picker's '(none)'
    # — the container skips the play for that class.
    for field in ("sound_id", "sound_success", "sound_warning", "sound_error"):
        value = getattr(update, field)
        if value is not None and value and not sounds.sound_exists(value):
            raise HTTPException(
                status_code=400,
                detail=f"Sound not found: {value}",
            )
    updates: dict = {}
    if update.suppressed is not None:
        updates["suppressed"] = update.suppressed
    if update.audio_enabled is not None:
        updates["audio_enabled"] = update.audio_enabled
    if update.sound_id is not None:
        updates["sound_id"] = update.sound_id
    if update.mute_until is not None:
        updates["mute_until"] = update.mute_until
    if update.volume is not None:
        updates["volume"] = update.volume
    for field in ("sound_success", "sound_warning", "sound_error"):
        value = getattr(update, field)
        if value is not None:
            updates[field] = value

    # THE SCHEDULED-MUTE (2026-08-29): suppressed=true + a mute_until
    # schedules the restore job; suppressed=false cancels it (the
    # restore-now clears the mute + removes the pending job — the
    # job's own expiry no-ops against a cleared config anyway).
    if update.suppressed is True:
        if update.mute_until is not None:
            try:
                notifications.schedule_mute_restore(update.mute_until)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    elif update.suppressed is False:
        notifications.cancel_mute_restore()
        updates.pop("mute_until", None)  # the restore-now clears the end

    # the restore-now clears the mute_until (a None value alone would
    # be skipped by the merge's None-guard — the clear is explicit)
    clear_keys = {"mute_until"} if update.suppressed is False else None
    return await save_notifications_config(db, updates, clear=clear_keys)
