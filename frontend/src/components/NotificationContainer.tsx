import { useCallback, useEffect, useRef, useState } from 'react'
import { ttsService } from '../services/ttsService';
import { ttsConfigService } from '../services/domain/ttsConfigService';
import { soundFileUrl } from '../services/domain/soundsService'
import { useNotificationStore } from '../stores/notificationStore'
import { useMessageStore } from '../stores/messageStore'
import { useNotificationConfigStore } from '../stores/notificationConfigStore'

// THE CLASS RANKS (2026-08-30, the sound-level): the sound_level
// config's the minimum class that pings — the ranks order the
// classes (info < success < warning < error).
const CLASS_RANK: Record<string, number> = { info: 0, success: 1, warning: 2, error: 3 }

export function NotificationContainer() {
  const { notifications, removeNotification, soundMutedIds, toggleToastSound } = useNotificationStore()
  // THE STICKY MODE (2026-08-31, the TTS P3): the tts-config's
  // sticky_mode — the container fetches it (the siren vs spoken).
  const [stickyMode, setStickyMode] = useState<'siren' | 'spoken'>('siren')
  const [ttsEnabled, setTtsEnabled] = useState(true)
  useEffect(() => {
    let alive = true
    ttsConfigService
      .getConfig()
      .then((cfg) => {
        if (alive) {
          setStickyMode(cfg.sticky_mode ?? 'siren')
          setTtsEnabled(cfg.enabled ?? true)
        }
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])
  // THE DISMISS-TOMBSTONE (2026-08-30, the Exa-diagnosed replay
  // bug): the ✕ must tombstone the event key — the bridge's
  // replay-check suppresses the sticky re-toast only when the
  // tombstone exists (the toast-✕ used to leave it empty, so the
  // next SSE ring-replay resurrected the sticky + the sound loop).
  const dismiss = (id: string, eventId?: string) => {
    removeNotification(id)
    if (eventId) {
      useMessageStore.getState().tombstoneKey(`evt:${eventId}`)
    }
  }
  const { config, load: loadNotificationConfig } = useNotificationConfigStore()
  // THE COPY BUTTON (2026-08-25, the user's ask): the toast's
  // message is ephemeral — the copy icon grabs the full text.
  const [copiedId, setCopiedId] = useState<string | null>(null)
  // THE SOUND-BLOCKED FLAG (2026-08-30, the user's no-sound report):
  // the browser's autoplay policy rejects the play until the first
  // page gesture — we now SURFACE it (no silent failures) with the
  // click-to-enable banner.
  const [soundBlocked, setSoundBlocked] = useState(false)

  // THE AUDIO PING (2026-08-29, the wav-assets): when the
  // notifications config has audio_enabled, a new toast plays the
  // selected sound (the Audio API — no libraries). The newest toast
  // is the LAST element (the store appends). One play per toast id;
  // the autoplay policy may block the very first play until the
  // user interacts with the page (stays silent then).
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const lastPlayedRef = useRef<string | null>(null)

  // THE CLASS->SOUND MAPPER (2026-08-30, the F4 design): the
  // container plays the class's wav — success -> the run-complete
  // bell, warning -> the alert, error -> the emergency; sound_id is
  // the fallback (info stays silent — the attention filter).
  //
  // DECLARED ABOVE THE PLAY-HOOKS, and memoized. Both effects below list it as
  // a dependency — they call it — and a dependency ARRAY is evaluated during
  // render, so a function declared below them would be a TDZ error; unmemoized,
  // its new identity every render would re-run both effects every render.
  const soundFor = useCallback((type: string) => {
    // THE PER-CLASS NONE (2026-08-31, the user's null-wav ask): the
    // configured EMPTY string is the class's silent — the play-hooks
    // skip it (the '??' falls back only when the field is absent).
    if (type === 'success') return config?.sound_success ?? config?.sound_id ?? 'gentle-ping.wav'
    if (type === 'warning') return config?.sound_warning ?? config?.sound_id ?? 'gentle-ping.wav'
    if (type === 'error') return config?.sound_error ?? config?.sound_id ?? 'gentle-ping.wav'
    return config?.sound_id ?? 'gentle-ping.wav'
  }, [config])

  useEffect(() => {
    loadNotificationConfig()
  }, [loadNotificationConfig])

  useEffect(() => {
    const newest = notifications[notifications.length - 1]
    if (!newest) return
    if (lastPlayedRef.current === newest.id) return
    if (!config?.audio_enabled || !config?.sound_id) return
    // THE SOUND LEVEL (2026-08-30, the user's ask): the MINIMUM
    // class that pings — "warning" by default (the alerts + the
    // emergencies; the run-complete bell is silent below the level).
    // Each class plays its own wav via soundFor().
    if (CLASS_RANK[newest.type] < (CLASS_RANK[config.sound_level] ?? 2)) return
    // THE STICKY DEFERS TO ITS OWN REPEAT (2026-08-30): the sticky
    // effect below owns the playback (the immediate play + the 2s
    // cycle) — this hook would double-play at mount.
    if (newest.sticky) return
    lastPlayedRef.current = newest.id
    if (audioRef.current) audioRef.current.pause()
    const sound = soundFor(newest.type)
    if (!sound) return // the per-class silent (the 'none')
    const audio = new Audio(soundFileUrl(sound))
    // THE VOLUME (2026-08-30, the user's ask): the config's loudness
    // rides the HTMLAudio volume (1.0 = the synthesized level).
    audio.volume = config.volume ?? 1
    audioRef.current = audio
    audio
      .play()
      .then(() => setSoundBlocked(false))
      .catch(() => {
        // THE AUTOPLAY POLICY (2026-08-30): the first play after a
        // page load is blocked until the first gesture — SURFACE it
        // (the click-to-enable banner) instead of the silent swallow.
        setSoundBlocked(true)
      })
  }, [
    soundMutedIds,
    stickyMode,
    ttsEnabled,
    // THE NEWEST NOTIFICATION — the array itself, not a hand-rolled
    // 'length ? [len-1].id : null': the rule cannot check an inline expression,
    // and the body reads the array anyway. The ref guard above still makes it
    // one play per toast id, so the extra runs are cheap no-ops.
    notifications,
    config?.audio_enabled,
    config?.sound_id,
    config?.sound_success,
    config?.sound_warning,
    config?.sound_error,
    config?.sound_level,
    config?.volume,
    soundFor,
  ])

  // THE STICKY REPEAT (2026-08-30, the user's ask — "the user
  // sometimes leaves the terminal"): a sticky attention-worthy toast
  // cycles its sound every 2s until it's DISMISSED (the newest
  // changes or the array empties -> the cleanup clears the interval).
  // THE MODE (2026-08-31, the TTS P3 build): the config's
  // sticky_mode decides — "siren" (the wav-loop, below) vs
  // "spoken" (the tts reads the alert's content ONCE — the content
  // delivered, the sticky stays).
  useEffect(() => {
    const newest = notifications[notifications.length - 1]
    if (!newest?.sticky) return
    if (CLASS_RANK[newest.type] < (CLASS_RANK[config?.sound_level ?? 'warning'] ?? 2)) return
    if (!config?.audio_enabled || !config?.sound_id) return

    // THE SPOKEN BRANCH (the P3): the content read once — the mute
    // respects it (the muted sticky stays silent).
    if (stickyMode === 'spoken') {
      if (ttsEnabled && !soundMutedIds.includes(newest.id)) {
        ttsService.speak(`${newest.title}. ${newest.message ?? ''}`)
      }
      return
    }

    const play = () => {
      // THE SOUND-MUTE (2026-08-31, the sticky dig's fix): the
      // per-toast mute stops the cycle WITHOUT dismissing.
      if (soundMutedIds.includes(newest.id)) return
      const sound = soundFor(newest.type)
    if (!sound) return // the per-class silent (the 'none')
    const audio = new Audio(soundFileUrl(sound))
      audio.volume = config.volume ?? 1
      audio
        .play()
        .then(() => setSoundBlocked(false))
        .catch(() => {
          // THE AUTOPLAY POLICY (2026-08-30): the blocked plays are
          // surfaced — the banner offers the one-click unlock; the
          // 2s cycle retries anyway (a gesture anywhere unlocks it).
          setSoundBlocked(true)
        })
    }
    play()
    const t = window.setInterval(play, 2000)
    return () => window.clearInterval(t)
  }, [
    soundMutedIds,
    stickyMode,
    ttsEnabled,
    // the array (see the note on the first play-hook) — it also carries the
    // newest toast's sticky flag, which the two inline ternaries tried to
    // single out; the guard above (non-sticky + one-play-per-id) is what
    // actually decides whether anything plays.
    notifications,
    config?.audio_enabled,
    config?.sound_id,
    config?.sound_success,
    config?.sound_warning,
    config?.sound_error,
    config?.sound_level,
    config?.volume,
    soundFor,
  ])

  const handleCopy = async (id: string, title: string, message: string, eventId?: string) => {
    try {
      // THE EVENT ID (2026-08-29, the user's ask): the toast copy
      // carries the bus event id — the same reference the center
      // records (the toast's random instance id is noise).
      const idLine = eventId ? `[event: ${eventId}] ` : ''
      await navigator.clipboard.writeText(`${idLine}${title}\n${message}`)
      setCopiedId(id)
      window.setTimeout(() => setCopiedId((cur) => (cur === id ? null : cur)), 1200)
    } catch {
      // the clipboard can be denied — the toast stays, no fuss
    }
  }

  const getAlertClass = (type: string) => {
    switch (type) {
      case 'success': return 'alert-success'
      case 'error': return 'alert-error'
      case 'warning': return 'alert-warning'
      case 'info': return 'alert-info'
      default: return 'alert-info'
    }
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'success':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      case 'error':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      case 'warning':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.35 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        )
      case 'info':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      default:
        return null
    }
  }

  if (notifications.length === 0) {
    return null
  }

  const handleUnlockAudio = () => {
    // THE ONE-CLICK UNLOCK (2026-08-30): the click IS the gesture the
    // policy waits for — play the configured sound + clear the flag;
    // the sticky repeat's next tick then plays naturally.
    const audio = new Audio(soundFileUrl(config?.sound_id ?? 'gentle-ping.wav'))
    audio.volume = config?.volume ?? 1
    audio
      .play()
      .then(() => setSoundBlocked(false))
      .catch(() => {
        /* the gesture may not have counted — the next click retries */
      })
  }

  return (
    <div className="toast toast-bottom toast-end z-50 max-w-[33vw] min-w-[280px]">
      {/* THE SOUND-BLOCKED BANNER (2026-08-30, the no-silent-failures
          doctrine): the browser's autoplay policy rejected the play —
          one click enables the audio alerts. */}
      {soundBlocked && (
        <button
          onClick={handleUnlockAudio}
          className="alert alert-warning shadow-lg mb-2 text-xs text-left cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
          </svg>
          <span>
            <strong>The browser blocked the sound</strong> — click here to play
            it and allow future audio alerts
          </span>
        </button>
      )}
      {/* THE STACK CAP (2026-08-22, the vision report): a backlog flood
          (the first workflow-toast poll with no cursor) rendered ~15
          stacked toasts — a solid wall covering the page. Cap the
          visible stack at 3; older ones are covered by the cursor
          advancing anyway. */}
      {notifications.slice(-3).map((notification) => (
        <div
          key={notification.id}
          className={`alert ${getAlertClass(notification.type)} shadow-lg mb-2 animate-in slide-in-from-right`}
        >
          <div className="flex items-start gap-3">
            {getIcon(notification.type)}
            <div className="flex-1 min-w-0">
              <h3 className="font-bold truncate">
                {notification.title}
                {notification.sticky && (
                  <span className="badge badge-sm badge-warning badge-outline ml-2">sticky</span>
                )}
              </h3>
              {/* whitespace-pre-line (2026-08-22, user): the toast
                  message can carry \n line breaks — the session-info
                  toast is a taller, formatted multi-line layout. */}
              <div className="text-xs break-words whitespace-pre-line">{notification.message}</div>
            </div>
            {notification.sticky && (
              <span className="tooltip tooltip-top" data-tip={soundMutedIds.includes(notification.id) ? 'Unmute the sound — the toast stays' : 'Mute the sound — the toast stays'}>
              <button
                className="btn btn-ghost btn-sm btn-circle shrink-0 transition-all duration-[var(--button-transition)]"
                onClick={() => toggleToastSound(notification.id)}
                aria-label={soundMutedIds.includes(notification.id) ? 'Unmute the toast sound' : 'Mute the toast sound'}
              >
                {soundMutedIds.includes(notification.id) ? (
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    <line x1={3} y1={3} x2={21} y2={21} strokeLinecap="round" />
                  </svg>
                )}
              </button>
              </span>
            )}
            <span className="tooltip tooltip-top" data-tip="Copy message">
            <button
              className="btn btn-ghost btn-sm btn-circle shrink-0 transition-all duration-[var(--button-transition)]"
              onClick={() => handleCopy(notification.id, notification.title, notification.message ?? '', notification.eventId)}
              aria-label="Copy message"
            >
              {copiedId === notification.id ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
            </span>
            <span className="tooltip tooltip-top" data-tip="Dismiss notification">
            <button
              className="btn btn-ghost btn-sm btn-circle shrink-0 transition-all duration-[var(--button-transition)]"
              aria-label="Dismiss notification"
              onClick={() => dismiss(notification.id, notification.eventId)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            </span>
          </div>
          {/* THE ACTION, RESTYLED (2026-08-22, user): its own line at the
              bottom, RIGHT-justified, a normal link with an arrow (not a
              button) — less prominent, offset from the message. */}
          {notification.action && (
            <div className="flex justify-end mt-2 pt-2 border-t border-base-content/10">
              {notification.action.href ? (
                <a
                  href={notification.action.href}
                  className="link link-primary link-hover text-xs flex items-center gap-1"
                >
                  {notification.action.label}
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                  </svg>
                </a>
              ) : notification.action.onClick ? (
                <button
                  onClick={notification.action.onClick}
                  className="link link-primary link-hover text-xs flex items-center gap-1"
                >
                  {notification.action.label}
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                  </svg>
                </button>
              ) : null}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}