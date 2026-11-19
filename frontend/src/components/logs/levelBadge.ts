/**
 * THE ONE LEVEL → BADGE MAP (2026-09-05, the ui-loudness Logs pass)
 *
 * Both LogsTable and LogDetailsModal used to carry their own
 * level→badge maps — and they drifted (one did `badge-ghost
 * text-white`, the other `bg-red-800` for critical). Consolidation
 * rule: DaisyUI THEME SEMANTICS ONLY — contrast rides the theme's
 * content pairings (badge-error = error-content text, etc.). No
 * text-white / text-base-content / bg-*-800 patches: they hardcoded
 * a color AND washed the pairing contrast. critical = badge-error
 * like error (the CRITICAL label + the font-weight carry the
 * escalation).
 */

export function getLevelBadge(level: string): { cls: string; label: string } {
  switch (level) {
    case 'error':
    case 'critical':
      return { cls: 'badge-error', label: level === 'critical' ? 'CRITICAL' : 'ERROR' }
    case 'warning':
      return { cls: 'badge-warning', label: 'WARNING' }
    case 'info':
      return { cls: 'badge-info', label: 'INFO' }
    case 'debug':
      return { cls: 'badge-ghost', label: 'DEBUG' }
    default:
      return { cls: 'badge-ghost', label: level.toUpperCase() }
  }
}
