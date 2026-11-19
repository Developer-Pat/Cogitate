import { useEffect, useState } from 'react'
import { usePageTitle } from '../hooks/usePageTitle'
import PageBanner from '../components/ui/PageBanner'

/* THE COMPONENT GALLERY (2026-09-07, the user's ask): one page under
   Development — the LIVE control/text vocabulary. Every sample renders
   the REAL classes, so switching the active theme re-samples the whole
   gallery. Each item = the live sample + the role name + the token/class
   it uses today. The point: SEE the vocabulary (incl. the gray tiers)
   before deciding what gets tokens. */

type TabId = 'controls' | 'badges' | 'text' | 'palette'

const TABS: { id: TabId; label: string }[] = [
  { id: 'controls', label: 'Controls' },
  { id: 'badges', label: 'Badges' },
  { id: 'text', label: 'Text' },
  { id: 'palette', label: 'Palette' },
]

function Sample({
  name,
  token,
  children,
}: {
  name: string
  token: string
  children: React.ReactNode
}) {
  return (
    <div className="card bg-base-100 border border-base-300 rounded-box p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 min-w-0">{children}</div>
        <div className="text-right shrink-0 max-w-[45%]">
          <div className="text-sm font-medium">{name}</div>
          <div className="text-[11px] text-base-content/50 font-mono break-all">{token}</div>
        </div>
      </div>
    </div>
  )
}

function ControlsTab() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <Sample name="Primary CTA — the one solid" token="btn btn-primary btn-sm">
        <button className="btn btn-primary btn-sm">Run now</button>
      </Sample>
      <Sample name="Semantic outlines — second tier" token="btn btn-<semantic> btn-outline btn-sm">
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-sm btn-success btn-outline">Success</button>
          <button className="btn btn-sm btn-error btn-outline">Error</button>
          <button className="btn btn-sm btn-warning btn-outline">Warning</button>
          <button className="btn btn-sm btn-info btn-outline">Info</button>
        </div>
      </Sample>
      <Sample name="Caution — the custom semantic" token="btn btn-caution btn-sm (--caution-bg)">
        <button className="btn btn-sm btn-caution">Caution</button>
      </Sample>
      <Sample name="Transfer — import/export" token="btn btn-transfer btn-sm (--transfer-bg)">
        <button className="btn btn-sm btn-transfer">Import</button>
      </Sample>
      <Sample name="Gray escape — stop / cancel" token="btn btn-neutral btn-sm">
        <button className="btn btn-neutral btn-sm">Cancel</button>
      </Sample>
      <Sample name="Selected state — the uniform on-state" token="btn btn-active btn-selected btn-sm">
        <button className="btn btn-sm btn-active btn-selected">Selected</button>
      </Sample>
      <Sample name="Checkbox — checks in action-blue" token="checkbox checkbox-sm checkbox-primary">
        <div className="flex items-center gap-3">
          <input type="checkbox" className="checkbox checkbox-sm checkbox-primary" defaultChecked readOnly />
          <input type="checkbox" className="checkbox checkbox-sm checkbox-primary" readOnly />
          <span className="text-xs text-base-content/60">enabled / idle</span>
        </div>
      </Sample>
      <Sample name="Toggle — the single on/off setting" token="toggle toggle-primary toggle-sm">
        <input type="checkbox" className="toggle toggle-primary toggle-sm" defaultChecked readOnly />
      </Sample>
      <Sample name="Input" token="input input-bordered input-sm">
        <input className="input input-bordered input-sm w-full max-w-[220px]" placeholder="Placeholder" readOnly />
      </Sample>
      <Sample name="Spinner — the busy state" token="loading loading-spinner text-primary">
        <span className="loading loading-spinner text-primary"></span>
      </Sample>
    </div>
  )
}

function BadgesTab() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <Sample name="Hue outlines — the status chips" token="badge badge-<semantic> badge-outline">
        <div className="flex flex-wrap gap-2">
          <span className="badge badge-primary badge-outline">primary</span>
          <span className="badge badge-success badge-outline">success</span>
          <span className="badge badge-warning badge-outline">warning</span>
          <span className="badge badge-error badge-outline">error</span>
          <span className="badge badge-info badge-outline">info</span>
        </div>
      </Sample>
      <Sample name="The access pair — Keyed vs GRAS" token="badge badge-warning/success badge-outline">
        <div className="flex flex-wrap gap-2">
          <span className="badge badge-warning badge-outline">Keyed</span>
          <span className="badge badge-success badge-outline">GRAS</span>
        </div>
      </Sample>
      <Sample name="Muted — the neutral-status gray" token="badge badge-muted badge-outline (--color-muted)">
        <span className="badge badge-muted badge-outline">shallow</span>
      </Sample>
      <Sample name="Ghost — the borderless quiet" token="badge badge-ghost">
        <span className="badge badge-ghost">unused</span>
      </Sample>
      <Sample name="Count bubble — the KEPT fill (attention)" token="badge badge-primary (filled)">
        <span className="badge badge-primary">3</span>
      </Sample>
    </div>
  )
}

const GRAY_TIERS = [20, 30, 40, 50, 60, 70, 80, 90]

function TextTab() {
  return (
    <div className="space-y-3">
      <Sample name="Body — the primary text" token=".text-body (--text-body = base-content)">
        <p className="text-sm text-body">The agent finished its sweep and reported two findings.</p>
      </Sample>
      <Sample name="Label — the field labels (the alias)" token=".text-label (--text-label: alias of the body — the weight does the work)">
        <label className="text-sm font-medium text-label">Display name</label>
      </Sample>
      <Sample name="Secondary / metadata — dates, counts, readouts" token=".text-readout (--text-readout = the named /65 tier)">
        <p className="text-sm text-readout">12:30 · 42 items · Updated 5 minutes ago</p>
      </Sample>
      <Sample name="Disabled / inactive — the gray’s intended home" token=".text-disabled (--text-disabled = the /40 tier, the dimmest)">
        <p className="text-sm text-disabled">Trigger paused — no runs scheduled</p>
      </Sample>
      <Sample name="Muted — the quietest tone (the badge-muted text side)" token=".text-muted (--text-muted = the theme-keyed muted)">
        <p className="text-sm text-muted">Shallow profile · no cognitive pipeline</p>
      </Sample>
      <Sample name="User chat — the ghost (rest state)" token="chat-bubble bubble-ghost · --chat-bubble-assistant-text">
        <div className="chat chat-end">
          <div className="chat-header opacity-70 text-xs mb-1">You</div>
          <div className="chat-bubble bubble-ghost max-w-[90%] text-[var(--chat-bubble-assistant-text)]">
            Summarize the market watch report.
          </div>
        </div>
      </Sample>
      <Sample name="The halo — the hover reveal" token="bubble-ghost:hover (the backlight glow — the ONLY selection cue)">
        <div className="chat chat-end">
          <div className="chat-header opacity-70 text-xs mb-1">You</div>
          <div
            className="chat-bubble bubble-ghost max-w-[90%] text-[var(--chat-bubble-assistant-text)]"
            style={{
              boxShadow:
                '0 0 0 1px color-mix(in oklch, var(--color-base-content) 7%, transparent), ' +
                '0 1px 2px color-mix(in oklch, var(--color-base-content) 10%, transparent), ' +
                '0 8px 24px color-mix(in oklch, var(--color-base-content) 18%, transparent)',
            }}
          >
            Summarize the market watch report.
          </div>
        </div>
      </Sample>
      <Sample name="Agent chat — the same ghost treatment" token="chat-bubble bubble-ghost w-[90%] (centered)">
        <div className="chat chat-start [&_.chat-bubble]:mx-auto">
          <div className="chat-header opacity-70 text-xs mb-1 text-center w-full">Assistant</div>
          <div className="chat-bubble bubble-ghost w-[90%] text-[var(--chat-bubble-assistant-text)]">
            Three findings landed in your inbox — the market watch caught two early movers.
          </div>
        </div>
      </Sample>

      <div className="card bg-base-100 border border-base-300 rounded-box p-4">
        <div className="mb-3">
          <div className="text-sm font-medium">The gray-tier ladder — what the overuse looks like</div>
          <div className="text-[11px] text-base-content/50 font-mono">text-base-content/&lt;tier&gt;</div>
        </div>
        <div className="space-y-2">
          {GRAY_TIERS.map((t) => (
            <div key={t} className="flex items-center gap-3">
              <span className={`text-sm text-base-content/${t} flex-1`}>
                Metadata sample — 12:30 · 42 items · Jan 5
              </span>
              <span className="text-[11px] text-base-content/50 font-mono w-24 text-right">/{t}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* THE PALETTE (2026-09-07, the user's ask): the ACTIVE theme's named
   colors, read live from the CSS vars — switch the theme and the
   MutationObserver re-samples the whole tab. */
const NAMED_COLORS = [
  'primary', 'primary-content',
  'secondary', 'secondary-content',
  'accent', 'accent-content',
  'neutral', 'neutral-content',
  'base-100', 'base-200', 'base-300', 'base-content',
  'info', 'info-content',
  'success', 'success-content',
  'warning', 'warning-content',
  'error', 'error-content',
] as const

function PaletteTab() {
  const [, force] = useState(0)
  useEffect(() => {
    const el = document.documentElement
    const mo = new MutationObserver(() => force((n) => n + 1))
    mo.observe(el, { attributes: true, attributeFilter: ['data-theme'] })
    return () => mo.disconnect()
  }, [])
  const theme = document.documentElement.dataset.theme || 'default'
  const swatches = NAMED_COLORS.map((name) => ({
    name,
    value: getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim(),
  }))
  return (
    <div className="space-y-3">
      <div className="text-sm text-base-content/60">
        The <span className="font-medium text-base-content">{theme}</span> theme's named palette — read live from the CSS
        variables; switch the theme in Settings and this re-samples.
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {swatches.map((s) => (
          <div key={s.name} className="card bg-base-100 border border-base-300 rounded-box p-3 flex items-center gap-3">
            <span
              className="h-10 w-10 rounded-lg shrink-0 border border-base-content/10"
              style={{ backgroundColor: s.value || 'transparent' }}
              aria-hidden
            />
            <div className="min-w-0">
              <div className="text-sm font-medium">{s.name}</div>
              <div className="text-[11px] text-base-content/50 font-mono truncate">{s.value || '—'}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ComponentGallery() {
  const [tab, setTab] = useState<TabId>('controls')
  usePageTitle('Gallery')
  return (
    <div className="p-6 space-y-5 max-w-5xl">
      <PageBanner
        title="Gallery"
        description="The live control + text vocabulary — each sample shows its role and the class/token it uses today. Switch the theme to see everything adapt."
      />
      <div className="flex gap-2 flex-wrap" role="tablist" aria-label="Vocabulary sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`btn btn-sm ${tab === t.id ? 'btn-active btn-selected' : 'btn-outline'}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'controls' && <ControlsTab />}
      {tab === 'badges' && <BadgesTab />}
      {tab === 'text' && <TextTab />}
      {tab === 'palette' && <PaletteTab />}
    </div>
  )
}
