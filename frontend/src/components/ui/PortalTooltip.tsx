import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

/**
 * PortalTooltip — a tooltip that ESCAPES scroll containers.
 *
 * WHY THIS EXISTS (2026-09-15). DaisyUI's `.tooltip` puts its text in an
 * absolutely-positioned `::before`. That is clipped by any ancestor with
 * `overflow: auto | hidden`. The sessions panel has FIVE such ancestors
 * (`.flex-1 overflow-y-auto`, an `overflow-hidden` root, the panel itself),
 * so the session-name tip had correct content and never appeared:
 *
 *     beforeContent:  "Local Weather 10-Day Forecast"   ← right text
 *     clippingAncestors: 5                              ← never seen
 *
 * This is NOT a styling bug and no CSS tweak fixes it: `overflow: visible`
 * cannot be set on a scroll container without breaking scrolling. The only
 * way out is to render the tip OUTSIDE the clipping tree — hence a portal to
 * `document.body` with `position: fixed` coordinates.
 *
 * WHY IT IS A SEPARATE COMPONENT, NOT A CHANGE TO ui/Tooltip.tsx: that
 * component was reduced to a bare DaisyUI wrapper on 2026-09-06 ("the
 * DaisyUI-only audit's find" — it replaced a hand-rolled JS bubble). The
 * audit was right for the ~hundreds of tips that live in unclipped space.
 * This is the narrow exception for the ones that do not, and it is OPT-IN:
 * nothing that works today goes through here.
 *
 * Styling follows DaisyUI's own tip (neutral surface, small text, rounded,
 * shadowed) so the two read as the same affordance.
 */

interface PortalTooltipProps {
  /** The tip text. Kept as one string so callers stay declarative. */
  content: string
  children: React.ReactNode
  /** Preferred side. Flips automatically when there is no room. */
  side?: 'top' | 'bottom'
  /** Cap so a long prompt cannot become a wall of text. */
  maxWidth?: number
  /** Let a caller suppress the tip without unmounting the child. */
  disabled?: boolean
}

const GAP = 6
/** Below this many px of room we flip to the other side. */
const MIN_ROOM = 64

export default function PortalTooltip({
  content,
  children,
  side = 'bottom',
  maxWidth = 420,
  disabled = false,
}: PortalTooltipProps) {
  const anchorRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null)

  const hide = useCallback(() => setPos(null), [])

  const show = useCallback(() => {
    const el = anchorRef.current
    if (!el || disabled || !content) return
    const r = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight

    // Room check decides the side; `side` is only a preference.
    const roomBelow = vh - r.bottom
    const wantBelow = side === 'bottom' ? roomBelow >= MIN_ROOM : roomBelow < MIN_ROOM

    // Width is clamped to the viewport so a long line still wraps inside it.
    const width = Math.min(maxWidth, vw - 16)

    // Horizontal: centre on the anchor, then clamp into the viewport. A tip
    // that hangs off the edge is as useless as one that is clipped.
    let left = r.left + r.width / 2 - width / 2
    left = Math.max(8, Math.min(left, vw - width - 8))

    // Vertical: the tip is rendered before it is measured, so we place it by
    // its TOP edge — below the anchor, or above it (using the anchor's top as
    // the ceiling and letting the box grow upward via translateY(-100%)).
    const top = wantBelow ? r.bottom + GAP : r.top - GAP

    setPos({ top, left, width })
    // `wantBelow` is not returned: the transform below encodes it, which keeps
    // this state a plain position rather than a second source of truth.
    ;(el as HTMLDivElement).dataset.tipBelow = wantBelow ? '1' : '0'
  }, [content, disabled, maxWidth, side])

  // A fixed-position tip would hang in space once its anchor scrolls away, so
  // any scroll closes it. capture:true catches the panel's internal scrollers.
  useEffect(() => {
    if (!pos) return
    const close = () => hide()
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [pos, hide])

  const below = anchorRef.current?.dataset.tipBelow !== '0'

  return (
    <>
      <div
        ref={anchorRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="min-w-0"
      >
        {children}
      </div>
      {pos &&
        createPortal(
          <div
            role="tooltip"
            className="pointer-events-none fixed z-[9999] rounded-lg bg-neutral px-2 py-1 text-xs leading-snug text-neutral-content shadow-lg"
            style={{
              top: pos.top,
              left: pos.left,
              width: pos.width,
              transform: below ? 'none' : 'translateY(-100%)',
              // Long prompts: wrap rather than overflow, and never run off-screen.
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              maxHeight: '40vh',
              overflow: 'hidden',
            }}
          >
            {content}
          </div>,
          document.body
        )}
    </>
  )
}
