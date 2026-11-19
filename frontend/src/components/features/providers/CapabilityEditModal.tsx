/**
 * CapabilityEditModal — ONE capability's chain, edited in the house modal shell.
 *
 * WHAT THIS REPLACES: an editor rendered INLINE, in place of the card's readout. An inline editor
 * has to hold its place inside the very list that is showing the chains, so the thing being edited
 * and the thing being ordered competed for one row — a card is roughly half the page, and an
 * attempt row (service form, provider, model, thinking, the move controls) wants the full width.
 * In the modal the readout STAYS where it is, behind the shell, and each attempt gets a line of its
 * own; dismissing the modal returns to exactly the list the reader was looking at.
 *
 * The rules the editor already carried, unchanged:
 * - the draft opens on the STORED chain (`configured`), NEVER on the resolution — the resolution can
 *   be an agent's declaration, expands a class candidate into every row it matches, and filters out
 *   rows switched OFF, so writing it back would quietly rewrite what the capability stores;
 * - the WHOLE chain is written on save, and a candidate's position in the list IS its ordinal;
 * - a refusal from the server keeps the modal OPEN with the server's own sentence, so the offending
 *   attempt can be fixed rather than the edit being lost.
 *
 * The shell is `ProviderModal` — the providers feature's working instance of the native
 * `<dialog className="modal">` + `showModal()` pattern — so Escape-to-close, focus containment and
 * focus return come for free. `onClose` fires for every dismissal: Cancel, the close control,
 * Escape, and a backdrop click.
 */
import { useMemo, useState, type ReactNode } from 'react'
import ProviderModal from './ProviderModal'
import { capabilitiesService } from '@/services/domains/providers/capabilitiesService'
import { THINKING_LEVELS } from '@/config/curatedModels'
import type {
  CapabilityCandidate,
  CapabilityCandidateInput,
  CapabilityReadout,
} from '@/types/capabilities'
import type { CuratedModel } from '@/config/curatedModels'
import type { ProviderConfig } from '@/types/providers'

/** The three ways an attempt can name its service, in the editor's words. */
const FORM_LABELS: Record<string, string> = {
  provider: 'Provider',
  location: 'Prefer a class',
  named: 'Named service',
}

/** One row of the editor's draft — the three forms flattened for form controls. */
type DraftRow = {
  form: 'provider' | 'location' | 'named'
  provider_id: number | null
  require_location: 'local' | 'cloud'
  service_name: string
  model: string
  thinking: string
  enabled: boolean
}

function draftFromStored(candidate: CapabilityCandidate): DraftRow {
  const form: DraftRow['form'] =
    candidate.provider_id !== null && candidate.provider_id !== undefined
      ? 'provider'
      : candidate.require_location
        ? 'location'
        : 'named'
  return {
    form,
    provider_id: candidate.provider_id ?? null,
    require_location: candidate.require_location === 'cloud' ? 'cloud' : 'local',
    service_name: candidate.service_name ?? '',
    model: candidate.model ?? '',
    thinking: candidate.thinking ?? '',
    enabled: candidate.enabled ?? true,
  }
}

function payloadFromDraft(row: DraftRow): CapabilityCandidateInput {
  return {
    provider_id: row.form === 'provider' ? row.provider_id : null,
    require_location: row.form === 'location' ? row.require_location : null,
    service_name: row.form === 'named' ? row.service_name.trim() : null,
    model: row.model.trim() || null,
    thinking: row.thinking || null,
    enabled: row.enabled,
  }
}

const EMPTY_ROW: DraftRow = {
  form: 'provider',
  provider_id: null,
  require_location: 'local',
  service_name: '',
  model: '',
  thinking: '',
  enabled: true,
}

/**
 * The chain-order control. A DISABLED button fires no hover, so its tooltip cannot live on the button
 * itself — and the disabled end rows are exactly where a reader wants to know why. So the tip moves
 * onto a wrapper for THAT state only; enabled, it stays on the button, because a wrapper around a
 * live control is a stray element in the flex row.
 */
function MoveButton({
  disabled,
  disabledTip,
  tip,
  label,
  onClick,
  children,
}: {
  disabled: boolean
  /** Shown while the control is unusable — the reason, not the action. */
  disabledTip: string
  tip: string
  label: string
  onClick: () => void
  children: ReactNode
}) {
  if (!disabled) {
    return (
      <button
        type="button"
        className="btn btn-xs btn-ghost"
        data-tip={tip}
        aria-label={label}
        onClick={onClick}
      >
        {children}
      </button>
    )
  }
  return (
    <span className="tooltip tooltip-left" data-tip={disabledTip}>
      <button type="button" className="btn btn-xs btn-ghost" disabled aria-label={label} onClick={onClick}>
        {children}
      </button>
    </span>
  )
}

interface CapabilityEditModalProps {
  capability: CapabilityReadout
  providers: ProviderConfig[]
  providersError: string | null
  /** The curated model lists (human-owned); a provider with none offers free text instead. */
  curated: CuratedModel[]
  curatedError: string | null
  onSaved: (updated: CapabilityReadout) => void
  onClose: () => void
}

/**
 * The curated lists keyed by the PROVIDER NAME the curated rows carry (`openrouter`, `llama`, …).
 *
 * The two sides name a provider differently — a curated row carries its provider's NAME, while an
 * attempt names its provider by ROW ID — so the row has to be resolved through the provider list
 * before the two can be matched.
 */
function curatedByProviderName(curated: CuratedModel[]): Record<string, CuratedModel[]> {
  const byProvider: Record<string, CuratedModel[]> = {}
  for (const model of curated) {
    ;(byProvider[model.provider] ??= []).push(model)
  }
  return byProvider
}

/**
 * The MODEL control — a picker over the curated list when the attempt's provider has one, free text
 * when it does not.
 *
 * WHY a picker at all: the model is the field most likely to be typed wrong, and a typo here is
 * silent — the capability resolves, the call fails, and the chain falls through to a backup the user
 * did not choose. The curated list is the human-vetted set for exactly this reason.
 *
 * THE OPTION'S VALUE IS THE MODEL ID, never the display name. A curated row carries both (`id` is
 * what the provider's API and the stored chain use, `name` is the human label); the agent-profile
 * picker learned this the hard way, and a display name saved here would be a model that does not
 * exist.
 *
 * TWO THINGS THE PICKER MUST NOT DO: drop an attempt's model that is not in the curated list (the
 * row keeps it as its own option, labelled), and invent one — the empty option is the provider row's
 * own default, which is what an empty `model` has always meant.
 */
function ModelField({
  row,
  index,
  providers,
  curatedByProvider,
  onChange,
}: {
  row: DraftRow
  index: number
  providers: ProviderConfig[]
  curatedByProvider: Record<string, CuratedModel[]>
  onChange: (model: string) => void
}) {
  const label = `Attempt ${index + 1}: model`
  const providerName =
    row.form === 'provider' && row.provider_id !== null
      ? (providers.find((provider) => provider.id === row.provider_id)?.name ?? null)
      : null
  const curated = providerName ? (curatedByProvider[providerName] ?? []) : []

  if (curated.length === 0) {
    return (
      <label className="form-control">
        <span className="label-text text-[11px] opacity-60">Model</span>
        <input
          type="text"
          className="input input-bordered input-xs w-40"
          placeholder="the row’s default"
          value={row.model}
          data-tip="The model to run; empty means the provider row's own default"
          aria-label={label}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    )
  }

  const orphan = row.model !== '' && !curated.some((model) => model.id === row.model)

  return (
    <label className="form-control">
      <span className="label-text text-[11px] opacity-60">Model</span>
      <select
        className="select select-bordered select-xs w-52"
        value={row.model}
        data-tip={`Pick from ${providerName}’s curated models; empty means the provider row's own default`}
        aria-label={label}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">the row’s default</option>
        {/* A stored model the curated list no longer carries stays selectable — otherwise opening
            the editor and saving would silently replace it with the row's default. */}
        {orphan && <option value={row.model}>{row.model} (not in the curated list)</option>}
        {curated.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name}
            {model.isFree ? ' (Free)' : ''}
            {model.verified ? ' ✓' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function CapabilityEditModal({
  capability,
  providers,
  providersError,
  curated,
  curatedError,
  onSaved,
  onClose,
}: CapabilityEditModalProps) {
  const title = capability.label || capability.key
  const [rows, setRows] = useState<DraftRow[]>(() => capability.configured.map(draftFromStored))
  const [enabled, setEnabled] = useState(capability.enabled)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const curatedByProvider = useMemo(() => curatedByProviderName(curated), [curated])

  const update = (index: number, patch: Partial<DraftRow>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)))

  const move = (index: number, delta: number) =>
    setRows((current) => {
      const next = [...current]
      const target = index + delta
      if (target < 0 || target >= next.length) return next
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await capabilitiesService.updateCapability(capability.key, {
        enabled,
        candidates: rows.map(payloadFromDraft),
      })
      onSaved(updated)
    } catch (err) {
      // The server's own sentence ("candidate 0: no provider with id …") is what tells the user
      // which attempt to fix, so it is shown as-is and the modal stays open.
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ProviderModal
      onClose={onClose}
      label={`Edit ${title} — its chain of services`}
      width="var(--dialog-width-xl)"
    >
      <div className="flex items-start justify-between gap-4 mb-4 pb-4 border-b border-base-300">
        <div>
          <h3 className="text-xl font-semibold text-base-content">{title}</h3>
          <p className="text-sm text-readout mt-1">
            Its chain of services, tried in order — the first attempt that answers wins, and
            everything below it is a backup. Saving replaces the whole chain, in the order below.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={onClose}
          aria-label="Close"
          data-tip="Close without saving"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {providersError && <p className="mb-3 text-xs text-error">{providersError}</p>}
      {curatedError && (
        <p className="mb-3 text-xs text-error">
          {curatedError} — the model field falls back to free text.
        </p>
      )}

      {rows.length === 0 && (
        <p className="mb-2 text-xs opacity-70">
          No attempt stored — this capability configures nothing of its own.
        </p>
      )}

      <div className="space-y-2">
        {rows.map((row, index) => (
          <div key={index} className="flex flex-wrap items-end gap-2">
            <label className="form-control">
              <span className="label-text text-[11px] opacity-60">Names its service by</span>
              <select
                className="select select-bordered select-xs w-36"
                value={row.form}
                data-tip="A provider row, a class of provider, or a named engine"
                aria-label={`Attempt ${index + 1}: how it names its service`}
                onChange={(e) => update(index, { form: e.target.value as DraftRow['form'] })}
              >
                {(['provider', 'location', 'named'] as const).map((form) => (
                  <option key={form} value={form}>
                    {FORM_LABELS[form]}
                  </option>
                ))}
              </select>
            </label>

            {row.form === 'provider' && (
              <label className="form-control">
                <span className="label-text text-[11px] opacity-60">Provider</span>
                <select
                  className="select select-bordered select-xs w-44"
                  value={row.provider_id ?? ''}
                  data-tip="The provider row to try"
                  aria-label={`Attempt ${index + 1}: provider`}
                  onChange={(e) =>
                    update(index, { provider_id: e.target.value ? Number(e.target.value) : null })
                  }
                >
                  <option value="">— pick a provider —</option>
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.display_name || provider.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {row.form === 'location' && (
              <label className="form-control">
                <span className="label-text text-[11px] opacity-60">Class</span>
                <select
                  className="select select-bordered select-xs w-28"
                  value={row.require_location}
                  data-tip="Every provider of this class, best first — 'prefer local' as configuration"
                  aria-label={`Attempt ${index + 1}: class`}
                  onChange={(e) =>
                    update(index, { require_location: e.target.value as 'local' | 'cloud' })
                  }
                >
                  <option value="local">local</option>
                  <option value="cloud">cloud</option>
                </select>
              </label>
            )}

            {row.form === 'named' && (
              <label className="form-control">
                <span className="label-text text-[11px] opacity-60">Engine or process</span>
                <input
                  type="text"
                  className="input input-bordered input-xs w-40"
                  placeholder="edge, whisper, exa…"
                  value={row.service_name}
                  data-tip="A named engine, as its own registry lists it"
                  aria-label={`Attempt ${index + 1}: named service`}
                  onChange={(e) => update(index, { service_name: e.target.value })}
                />
              </label>
            )}

            <ModelField
              row={row}
              index={index}
              providers={providers}
              curatedByProvider={curatedByProvider}
              onChange={(model) => update(index, { model })}
            />

            <label className="form-control">
              <span className="label-text text-[11px] opacity-60">Thinking</span>
              <select
                className="select select-bordered select-xs w-28"
                value={row.thinking}
                data-tip="The thinking level this attempt is for; empty means any"
                aria-label={`Attempt ${index + 1}: thinking`}
                onChange={(e) => update(index, { thinking: e.target.value })}
              >
                <option value="">any</option>
                {THINKING_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>

            {/* The move/remove controls stay at the row's RIGHT edge — when the controls above them
                fill the line these wrap to a second line, and right-aligned they read as that
                attempt's own controls rather than as a new row. */}
            <div className="ml-auto flex gap-1">
              <MoveButton
                disabled={index === 0}
                disabledTip="Already first"
                tip="Move this attempt earlier"
                label={`Move attempt ${index + 1} earlier`}
                onClick={() => move(index, -1)}
              >
                Up
              </MoveButton>
              <MoveButton
                disabled={index === rows.length - 1}
                disabledTip="Already last"
                tip="Move this attempt later"
                label={`Move attempt ${index + 1} later`}
                onClick={() => move(index, 1)}
              >
                Down
              </MoveButton>
              <button
                type="button"
                className="btn btn-xs btn-ghost text-error"
                data-tip="Remove this attempt from the chain"
                aria-label={`Remove attempt ${index + 1}`}
                onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>

      {saveError && <p className="mt-3 text-xs text-error">{saveError}</p>}

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-base-300 pt-4">
        <button
          type="button"
          className="btn btn-xs btn-outline"
          data-tip="Add another attempt at the end of the chain"
          onClick={() => setRows((current) => [...current, { ...EMPTY_ROW }])}
        >
          Add a service
        </button>

        <label className="label cursor-pointer gap-2 py-0">
          <input
            type="checkbox"
            className="toggle toggle-sm"
            checked={!enabled}
            data-tip="Off: nothing resolves for this capability, and a consumer refuses instead of falling back"
            aria-label="Off"
            onChange={(e) => setEnabled(!e.target.checked)}
          />
          <span className="label-text text-xs">Off</span>
        </label>

        <div className="ml-auto flex gap-2">
          <button
            type="button"
            className="btn btn-sm"
            data-tip="Leave the stored chain as it is"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-sm btn-primary"
            disabled={saving}
            data-tip="Replace this capability's whole chain"
            onClick={() => void save()}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </ProviderModal>
  )
}
