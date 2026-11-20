/**
 * CuratedModelsManager — in-app management UI for the curated model list.
 *
 * Phase 3 admin UX: humans own the curated list (recommendations shown in
 * ProfileDetail + curatedModels.ts seed). This component provides full
 * CRUD against /api/v1/curated-models (built in Phase 1).
 *
 * Features:
 * - Provider filter (a select, `All` included; the counts ride in its options)
 * - Table: provider, display name, model id (both truncated, both with the full value in a
 *   tooltip), cost (free/paid), thinking, actions (copy / verify / edit / remove) — sorted by
 *   whichever header is pressed
 * - Add-modal: provider, model id, name, category, context, the two capability
 *   dimensions (thinking, location), flags
 * - Inline edit (modal) + delete with confirmation
 * - Verify dialog: one row's window against the provider's own catalog claim
 * - Toasts on every mutation
 */

import { useState, useEffect, useCallback } from 'react'
import { Copy, Pencil, Trash2 } from 'lucide-react'
import type { components } from '@/types/api.generated'
import {
  fetchCuratedModels,
  addCuratedModel,
  updateCuratedModel,
  removeCuratedModel,
  verifyCuratedModelWindow,
  type CuratedWindowVerification,
} from '@/services/domains/providers/curatedModelsService'
import {
  THINKING_LEVELS,
  MODEL_LOCATIONS,
  type CuratedModel,
  type ThinkingLevel,
  type ModelLocation,
} from '@/config/curatedModels'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'

const CATEGORIES = ['chat', 'code', 'reasoning', 'vision'] as const
type Category = (typeof CATEGORIES)[number]

interface CuratedModelsManagerProps {
  providers: components['schemas']['ProviderConfig'][]
  loading: boolean
}

interface FormState {
  id: string
  name: string
  provider: string
  category: Category | ''
  description: string
  contextLength: string
  /** 'auto' = take the provider's own claim (create only; never a stored value). */
  thinking: ThinkingLevel | 'auto'
  location: ModelLocation
}

const EMPTY_FORM: FormState = {
  id: '',
  name: '',
  provider: '',
  category: '',
  description: '',
  contextLength: '',
  thinking: 'auto',
  location: 'cloud',
}

/**
 * The table's own sort — CLIENT-SIDE on purpose.
 *
 * The list is unpaginated (12 rows), so the ordering belongs to the reader. The server
 * orders by `(provider, model_id)` — its guarantee to a client that does not sort; the
 * number it used to order by is gone (the arc's Phase 2).
 *
 * The tie-break follows the COLUMNS' reading order — provider, then name, then the model id —
 * so a descending press never scrambles rows that are equal on the primary key, and the
 * always-ascending fallback agrees with what the eye reads next. The id is LAST of the three
 * on purpose: it is a provider-side spelling that sorts `~deepseek/…` at the very end (0x7E),
 * which reads as a shuffle beside the names it now sits after.
 */
type SortKey =
  | 'id'
  | 'provider'
  | 'name'
  | 'cost'
  | 'thinking'

interface SortState {
  key: SortKey
  dir: 'asc' | 'desc'
}

/** Default order: provider, then name, then model id. */
const DEFAULT_SORT: SortState = { key: 'provider', dir: 'asc' }

function sortValue(m: CuratedModel, key: SortKey): string | number {
  switch (key) {
    case 'id': return m.id
    case 'provider': return m.provider ?? ''
    case 'name': return m.name
    // THE COST SORT, in the matcher's OWN order (Phase 4): free, then paid, then unpriced —
    // so the table and the substitution matcher agree about what a person wants first, and an
    // unknown cost does not outrank a stated one.
    case 'cost': return m.isFree === true ? 0 : m.isFree === false ? 1 : 2
    // The vocabulary's OWN order (none -> low -> medium -> high -> mandatory), not the
    // alphabet. A value no vocabulary lists sorts LAST rather than posing as 'none'.
    case 'thinking': {
      const i = THINKING_LEVELS.indexOf(m.thinking ?? 'none')
      return i === -1 ? THINKING_LEVELS.length : i
    }
  }
}

/** A claim's age in words a person reads: a fresh fetch is "just now", not 0.00009h. */
function claimAge(ageHours: number | null): string {
  if (ageHours == null) return 'an unrecorded age'
  if (ageHours < 0.1) return 'just now'
  return `${ageHours >= 10 ? Math.round(ageHours) : ageHours.toFixed(1)}h old`
}

function sortModels(rows: CuratedModel[], sort: SortState): CuratedModel[] {
  const sign = sort.dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = sortValue(a, sort.key)
    const bv = sortValue(b, sort.key)
    const primary = typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv))
    return primary !== 0 ? primary * sign : (a.name.localeCompare(b.name) || a.id.localeCompare(b.id))
  })
}

/** A header that sorts. `width` fixes the column under `table-fixed`, which is what makes the
 *  long cells truncate instead of stretching the table. */
function SortHeader({ label, sortKey, sort, onSort, align = 'left', tip, width }: {
  label: string
  sortKey: SortKey
  sort: SortState
  onSort: (key: SortKey) => void
  align?: 'left' | 'center' | 'right'
  tip: string
  width?: string
}) {
  const active = sort.key === sortKey
  const alignment = align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : ''
  return (
    <th
      className={width ? `${alignment} ${width}`.trim() : alignment || undefined}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <span className="tooltip tooltip-top" data-tip={tip}>
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          aria-label={`Sort by ${label}`}
          className="btn btn-ghost btn-xs gap-1 font-normal"
        >
          {label}{active && (sort.dir === 'asc' ? ' ↑' : ' ↓')}
        </button>
      </span>
    </th>
  )
}

export default function CuratedModelsManager({ providers }: CuratedModelsManagerProps) {
  const [models, setModels] = useState<CuratedModel[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [modelsLoading, setModelsLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editing, setEditing] = useState<(CuratedModel & { curatedRowId: number }) | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT)
  const [verifyTarget, setVerifyTarget] = useState<(CuratedModel & { curatedRowId: number }) | null>(null)
  const [verifyResult, setVerifyResult] = useState<CuratedWindowVerification | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)

  /**
   * Pressing the active header flips its direction; pressing another takes the order
   * over, ascending. Which DIRECTION the reader wants is theirs; the tie-break stays
   * ascending either way.
   */
  const toggleSort = (key: SortKey) => {
    setSort(prev => prev.key === key
      ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: 'asc' })
  }

  const load = useCallback(async () => {
    try {
      setModelsLoading(true)
      const data = await fetchCuratedModels()
      setModels(data)
    } catch (err) {
      frontendLoggingService.error('CuratedModelsManager', 'Failed to load curated models', err)
      useNotificationStore.getState().addError('Load Failed', 'Could not load curated models')
    } finally {
      setModelsLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const providersList = providers.length > 0
    ? providers
    : [{ id: 0, name: 'openrouter', display_name: 'OpenRouter' },
       { id: 0, name: 'ollama', display_name: 'Ollama' },
       { id: 0, name: 'deepseek', display_name: 'DeepSeek' },
       { id: 0, name: 'ollama_cloud', display_name: 'Ollama Cloud' }]

  const providerNames = [...new Set([...providersList.map(p => p.name), ...models.map(m => m.provider)])].sort()
  const filtered = filter === 'all' ? models : models.filter(m => m.provider === filter)

  const openAdd = (providerName?: string) => {
    setForm({ ...EMPTY_FORM, provider: providerName || (filter !== 'all' ? filter : 'openrouter') })
    setEditing(null)
    setShowAddModal(true)
  }

  const openEdit = (m: CuratedModel & { curatedRowId: number }) => {
    setEditing(m)
    setForm({
      id: m.id,
      name: m.name,
      provider: m.provider,
      category: (m.category as Category) || '',
      description: m.description || '',
      contextLength: m.contextLength != null ? String(m.contextLength) : '',
      thinking: m.thinking || 'none',
      location: m.location || 'cloud',
    })
    setShowAddModal(true)
  }

  const handleSave = async () => {
    if (!form.id.trim() || !form.name.trim() || !form.provider.trim()) {
      useNotificationStore.getState().addError('Missing Fields', 'Model ID, name, and provider are required')
      return
    }
    setSaving(true)
    try {
      const payload = {
        id: form.id.trim(),
        name: form.name.trim(),
        provider: form.provider.trim(),
        // `undefined` travels as "nobody chose" and the create payload then OMITS the key —
        // the row stores "not described" rather than a word no one picked.
        category: form.category || undefined,
        description: form.description.trim() || null,
        contextLength: form.contextLength ? Number(form.contextLength) : undefined,
        // `undefined` travels as "nobody chose" all the way to the API, which derives
        // the level from the provider's own claim.
        thinking: form.thinking === 'auto' ? undefined : form.thinking,
        location: form.location,
      }
      if (editing) {
        await updateCuratedModel(editing.curatedRowId, {
          model_name: payload.name,
          // An explicit null CLEARS the descriptor; an absent field leaves it alone. The empty
          // selection is a real choice here, so it has to be sendable.
          category: payload.category || null,
          description: payload.description,
          context_length: payload.contextLength ?? null,
          thinking: payload.thinking,
          location: payload.location,
        })
        useNotificationStore.getState().addSuccess('Updated', `"${payload.name}" updated`)
      } else {
        await addCuratedModel(payload as never)
        useNotificationStore.getState().addSuccess('Added', `"${payload.name}" added to curated list`)
      }
      setShowAddModal(false)
      await load()
    } catch (err) {
      frontendLoggingService.error('CuratedModelsManager', 'Save failed', err)
      useNotificationStore.getState().addError('Save Failed', err instanceof Error ? err.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (m: CuratedModel & { curatedRowId: number }) => {
    if (!window.confirm(`Remove "${m.name}" from the curated list?`)) return
    try {
      await removeCuratedModel(m.curatedRowId)
      useNotificationStore.getState().addSuccess('Removed', `"${m.name}" removed from curated list`)
      await load()
    } catch (err) {
      frontendLoggingService.error('CuratedModelsManager', 'Delete failed', err)
      useNotificationStore.getState().addError('Delete Failed', err instanceof Error ? err.message : 'Could not remove')
    }
  }

  /**
   * The row's FULL model id onto the clipboard — read from the row's OWN data, never from the
   * cell the table truncated. That distinction IS the button: the column clips the id to a
   * fixed width, and this is how you get the exact spelling an agent needs.
   */
  const copyModelId = async (row: CuratedModel) => {
    try {
      await navigator.clipboard.writeText(row.id)
      useNotificationStore.getState().addSuccess('Copied', `Model id copied: ${row.id}`)
    } catch (err) {
      frontendLoggingService.error('CuratedModelsManager', 'Copy failed', err)
      useNotificationStore.getState().addError('Copy Failed', 'The clipboard could not be written')
    }
  }

  const openVerify = (m: CuratedModel & { curatedRowId: number }) => {
    setVerifyTarget(m)
    setVerifyResult(null)
    setVerifyError(null)
  }

  const closeVerify = () => {
    setVerifyTarget(null)
    setVerifyResult(null)
    setVerifyError(null)
  }

  /**
   * The check itself. `refresh` is the ONE question this dialog asks — read the claim
   * our discovery fetch recorded, or ask the provider again now. The row may ADOPT the
   * provider's number and its reasoning claim, so the list is re-read afterwards.
   */
  const runVerify = async (refresh: boolean) => {
    if (!verifyTarget) return
    setVerifying(true)
    setVerifyError(null)
    try {
      const result = await verifyCuratedModelWindow(verifyTarget.curatedRowId, refresh)
      setVerifyResult(result)
      await load()
    } catch (err) {
      frontendLoggingService.error('CuratedModelsManager', 'Verify failed', err)
      setVerifyError(err instanceof Error ? err.message : 'The check could not run')
    } finally {
      setVerifying(false)
    }
  }

  /**
   * The row as it stands NOW. A check may adopt the provider's number and `load()`
   * re-reads the list, so the dialog's own header must not keep quoting the old value.
   */
  const verifyRow: (CuratedModel & { curatedRowId: number }) | null = verifyTarget
    ? ((models.find(m => (m as CuratedModel & { curatedRowId: number }).curatedRowId === verifyTarget.curatedRowId) as (CuratedModel & { curatedRowId: number }) | undefined) ?? verifyTarget)
    : null

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="text-lg font-semibold text-base-content">Curated Models</h3>
          <p className="text-sm text-readout mt-0.5">
            Human-owned recommendations shown in agent setup. The DB is the source of truth
            (config seed is fallback only).
          </p>
        </div>
        <button
          type="button"
          onClick={() => openAdd()}
          className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
        >
          + Add Model
        </button>
      </div>

      {/* Provider filter — a SELECT, not a pill row: the pills' selection differed only by a
          fill, and the counts ride in the option labels so the readout the pills carried
          survives. `All` is the default — a filter that hides eleven rows on open is how an
          operator loses sight of their own data. */}
      <div className="flex items-center gap-2">
        <label className="label py-0" htmlFor="curated-provider-filter">
          <span className="label-text text-sm">Provider</span>
        </label>
        <span className="tooltip tooltip-top" data-tip="Narrow the table to one provider">
          <select
            id="curated-provider-filter"
            aria-label="Filter by provider"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            disabled={modelsLoading}
            className="select select-bordered select-sm"
          >
            <option value="all">All ({models.length})</option>
            {providerNames.map(name => (
              <option key={name} value={name}>
                {name} ({models.filter(m => m.provider === name).length})
              </option>
            ))}
          </select>
        </span>
      </div>

      {/* Table */}
      {modelsLoading ? (
        <div className="flex items-center justify-center py-10">
          <span className="loading loading-spinner loading-md text-primary" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-10 text-readout text-sm bg-base-200 rounded-lg">
          No curated models{filter !== 'all' ? ` for ${filter}` : ''}. Add one to get started.
        </div>
      ) : (
        <div className="overflow-x-auto bg-base-200 rounded-lg border border-base-300">
          <table className="table table-sm table-fixed w-full">
            <thead>
              <tr className="text-readout">
                {/* ORDER FOLLOWS THE SCAN: which provider, what we call it, its exact spelling.
                    The two long cells are fixed-width (see `table-fixed` below) so they truncate
                    instead of stretching the table, each with its full value in a tooltip. */}
                <SortHeader label="Provider" sortKey="provider" sort={sort} onSort={toggleSort}
                  width="w-[110px]"
                  tip="Which provider serves this model — the pair (provider, model id) identifies a row. Press to sort by it." />
                <SortHeader label="Name" sortKey="name" sort={sort} onSort={toggleSort}
                  width="w-[200px]"
                  tip="Press to sort by display name. A long name is truncated here; the tooltip shows it whole." />
                <SortHeader label="Model" sortKey="id" sort={sort} onSort={toggleSort}
                  width="w-[230px]"
                  tip="The provider's own model id — the exact spelling an agent is saved with. Press to sort; the Copy action takes it whole." />
                <SortHeader label="Cost" sortKey="cost" sort={sort} onSort={toggleSort} align="center"
                  width="w-[110px]"
                  tip="Free, paid, or unpriced — read from the provider's own catalog when the row was created. Press to gather the free models together." />
                <SortHeader label="Thinking" sortKey="thinking" sort={sort} onSort={toggleSort} align="center"
                  width="w-[100px]"
                  tip="Press to sort by declared thinking level, in the vocabulary's own order." />
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortModels(filtered, sort).map(m => {
                  const row = m as CuratedModel & { curatedRowId: number }
                  // `data-model-id` is the row's IDENTITY on the DOM, so a test (or a future
                  // column reorder) never has to count cells: this very change moved the id from
                  // the first cell to the third, which would have re-pointed an index silently.
                  return (
                    <tr key={row.curatedRowId ?? row.id} data-model-id={row.id} className="hover:bg-base-300/50">
                      <td>{row.provider}</td>
                      <td>
                        {/* Truncated to the column's fixed width, full value in the tooltip —
                            and because CSS truncation leaves the text in the DOM, it stays
                            selectable rather than becoming hover-only. */}
                        {/* THE NOTE READS HERE — this is the description's read path. A row's
                            description is "extended per-item" content: it does not take a column
                            (the user's ruling) and it must not need a second surface either. The
                            name is where a person asks WHAT this model is, so its tooltip carries
                            the full name — the column truncates — and, when the row has one, the
                            note. A row with no note is untouched: the tooltip is then just the
                            name, and nothing is invented for it. */}
                        <div
                          className="tooltip tooltip-top w-full"
                          data-tip={row.description ? `${row.name} — ${row.description}` : row.name}
                        >
                          <div className="truncate">{row.name}</div>
                        </div>
                      </td>
                      <td>
                        <div className="tooltip tooltip-top w-full" data-tip={row.id}>
                          <div className="truncate font-mono text-xs">{row.id}</div>
                        </div>
                      </td>
                      <td className="text-center">
                        {/* ONE COLUMN FOR THE COST FACT (R1), and the fact is DERIVED (Phase 4):
                            the row carries what the provider's own pricing said when it was
                            created. "unpriced" is a real third answer — the catalog states no
                            price for this model — not a default dressed up as one. */}
                        <span className="tooltip tooltip-top" data-tip={
                          row.isFree === true
                            ? 'Free on this provider — the catalog prices it at zero'
                            : row.isFree === false
                              ? 'Paid — this provider charges for this model'
                              : "Unpriced — this provider's catalog states no price for this model"
                        }>
                          <span className={
                            row.isFree === true
                              ? 'badge badge-sm badge-success badge-outline'
                              : row.isFree === false
                                ? 'badge badge-sm badge-ghost'
                                : 'badge badge-sm badge-outline'
                          }>
                            {row.isFree === true ? 'free' : row.isFree === false ? 'paid' : 'unpriced'}
                          </span>
                        </span>
                      </td>
                      <td className="text-center">
                        <span
                          className="tooltip tooltip-top"
                          data-tip={row.thinking === 'mandatory'
                            ? 'Cannot be told not to think — the output-budget floor is a property of the driver'
                            : 'Declared thinking level — it ranks the substitution matcher and floors the output budget'}
                        >
                          <span
                            className={
                              row.thinking === 'mandatory'
                                ? 'badge badge-sm badge-warning badge-outline'
                                : 'badge badge-sm badge-ghost'
                            }
                          >
                            {row.thinking || 'none'}
                          </span>
                        </span>
                      </td>
                      <td className="text-right whitespace-nowrap">
                        <span className="tooltip tooltip-top" data-tip="Copy the full model id">
                          <button
                            type="button"
                            onClick={() => copyModelId(row)}
                            className="btn btn-ghost btn-xs"
                            aria-label={`Copy model id for ${row.name}`}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </button>
                        </span>
                        {/* THE VERIFY ACTION LIVES HERE, not in a column of its own: every
                            row in this table is already verified (12/12 on the live data),
                            so a column carrying the state said nothing — and R2 keeps the
                            state in the dialog. The check stays one press away because it is
                            what FILLS a row's window, and 10 of the 12 have none. */}
                        <span className="tooltip tooltip-top" data-tip="Check this row against the provider's own claim">
                          <button
                            type="button"
                            onClick={() => openVerify(row)}
                            className="btn btn-ghost btn-xs"
                            aria-label={`Verify ${row.name}`}
                          >
                            Verify
                          </button>
                        </span>
                        <span className="tooltip tooltip-top" data-tip="Edit curated entry">
                          <button
                            type="button"
                            onClick={() => openEdit(row)}
                            className="btn btn-ghost btn-xs"
                            aria-label="Edit curated entry"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        </span>
                        <span className="tooltip tooltip-top" data-tip="Remove curated entry">
                          <button
                            type="button"
                            onClick={() => handleDelete(row)}
                            className="btn btn-ghost btn-xs text-error"
                            aria-label="Remove curated entry"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/Edit Modal — the dev-note template VERBATIM
          (`wiki/dev-notes/frontend/modal-dialogs.md`): the fixed overlay with the width
          token and `p-6`; never DaisyUI's `modal-box` (48px wide in this Tailwind v4
          setup) and never `max-w-*` (which resolves against the SPACING namespace, so
          `max-w-lg` is 24px). Measured before this fix: a 24px panel that the form
          overflowed, 944px tall inside a 577px viewport — its title off the top and its
          Save button below the fold, with nothing scrollable in between. */}
      {showAddModal && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-label={editing ? `Edit ${editing.name}` : 'Add Curated Model'}
          onClick={() => { if (!saving) setShowAddModal(false) }}
        >
          <div
            className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
            style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-base-content mb-4">
              {editing ? `Edit ${editing.name}` : 'Add Curated Model'}
            </h3>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="form-control">
                  <label className="label"><span className="label-text font-semibold">Provider *</span></label>
                  <select
                    value={form.provider}
                    onChange={e => setForm({ ...form, provider: e.target.value })}
                    disabled={saving || !!editing}
                    className="select select-bordered select-sm"
                  >
                    {providerNames.map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                <div className="form-control">
                  <label className="label"><span className="label-text font-semibold">Category</span></label>
                  {/* OPTIONAL, and NOTHING IS PRE-SELECTED: the empty option is the state of a row
                      nobody has described, which is why it comes first. A value here is a
                      one-word descriptor of what the model is FOR — the cost fact is the Free
                      toggle's, and the table's Cost column. */}
                  <select
                    value={form.category}
                    onChange={e => setForm({ ...form, category: e.target.value as Category | '' })}
                    disabled={saving}
                    aria-label="Category"
                    className="select select-bordered select-sm"
                  >
                    <option value="">— not described —</option>
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-control">
                <label className="label"><span className="label-text font-semibold">Model ID *</span></label>
                <input
                  type="text"
                  value={form.id}
                  onChange={e => setForm({ ...form, id: e.target.value })}
                  disabled={saving || !!editing}
                  placeholder="e.g. nvidia/nemotron-3-super-120b-a12b:free"
                  className="input input-bordered input-sm font-mono"
                />
              </div>
              <div className="form-control">
                <label className="label"><span className="label-text font-semibold">Display Name *</span></label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  disabled={saving}
                  placeholder="e.g. NVIDIA: Nemotron 3 Super"
                  className="input input-bordered input-sm"
                />
              </div>
              <div className="form-control">
                <label className="label"><span className="label-text font-semibold">Description</span></label>
                {/* The note has a read path: it shows on this row's NAME tooltip in the table.
                    It is deliberately not a column — "extended per-item descriptions belong
                    elsewhere" (the user's ruling) — and this field is where it is written. */}
                <div
                  className="tooltip tooltip-top w-full"
                  data-tip="What this model is good for, in your words. It reads on the model's name tooltip in the table, not in a column."
                >
                  <textarea
                    value={form.description}
                    onChange={e => setForm({ ...form, description: e.target.value })}
                    disabled={saving}
                    rows={3}
                    className="textarea textarea-bordered textarea-sm"
                  />
                </div>
              </div>
              <div className="form-control">
                <label className="label"><span className="label-text font-semibold">Context Length (tokens)</span></label>
                <div
                  className="tooltip tooltip-top w-full"
                  data-tip="The model's context window. The provider's own catalogue number WINS at create, so a disagreeing value is replaced and logged. It can only LOWER the app's 16,000-token input budget, never raise it — worth setting for a small local model so a turn is trimmed instead of rejected; leave it empty if unknown, because unknown does not clamp."
                >
                  <input
                    type="number"
                    value={form.contextLength}
                    onChange={e => setForm({ ...form, contextLength: e.target.value })}
                    disabled={saving}
                    placeholder="e.g. 262144"
                    className="input input-bordered input-sm w-full"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="form-control">
                  <label className="label"><span className="label-text font-semibold">Thinking</span></label>
                  <div
                    className="tooltip tooltip-top w-full"
                    data-tip="What this driver declares about thinking. The provider's own claim WINS at create, so a payload saying its reasoning is mandatory is recorded as 'mandatory' and a stated level that disagrees is replaced and logged. 'auto' is the honest default: nobody has chosen, so the provider's record decides. Edit a row afterwards to state a level of your own. This ranks the substitution matcher and floors the output budget."
                  >
                    <select
                      value={form.thinking}
                      onChange={e => setForm({ ...form, thinking: e.target.value as ThinkingLevel | 'auto' })}
                      disabled={saving}
                      aria-label="Thinking"
                      className="select select-bordered select-sm w-full"
                    >
                      {!editing && <option value="auto">auto — the provider's claim</option>}
                      {THINKING_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </div>
                </div>
                <div className="form-control">
                  <label className="label"><span className="label-text font-semibold">Location</span></label>
                  <div
                    className="tooltip tooltip-top w-full"
                    data-tip="Where this model runs: 'local' for a server on this machine, 'cloud' for a provider."
                  >
                    <select
                      value={form.location}
                      onChange={e => setForm({ ...form, location: e.target.value as ModelLocation })}
                      disabled={saving}
                      aria-label="Location"
                      className="select select-bordered select-sm w-full"
                    >
                      {MODEL_LOCATIONS.map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </div>
                </div>
              </div>
              <div className="flex gap-6">
                {/* NO FREE TOGGLE (Phase 4): the cost is DERIVED from the provider's own cached
                    pricing as the row is created, and the API refuses a request that states it —
                    so a switch here would have been a control that decides nothing. It also has
                    a third answer now ("unpriced"), which a checkbox cannot express. */}
                <p className="text-xs text-readout">
                  Verification is an action, not a flag: a row's Verify button checks its
                  context window against the provider's own catalog claim, and the result
                  says whether it agreed.
                  {editing && (editing.verified
                    ? <span className="text-success"> This model is currently verified.</span>
                    : <span> This model is not yet verified.</span>)}
                </p>
              </div>
            </div>
            <div className="modal-action">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                disabled={saving}
                className="btn btn-ghost btn-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)]"
              >
                {saving ? 'Saving...' : editing ? 'Save Changes' : 'Add Model'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Verify dialog — ONE row's window against the provider's own catalog claim. The
          same house template as the edit modal (`wiki/dev-notes/frontend/modal-dialogs.md`).
          The dialog names the ROW'S WINDOW, never "connectivity": the provider cards' Test
          one level up is the connectivity check, and this is not it. */}
      {verifyRow && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-label={`Verify ${verifyRow.name}`}
          onClick={() => { if (!verifying) closeVerify() }}
        >
          <div
            className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
            style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-base-content mb-1">
              {`Verify ${verifyRow.name}`}
            </h3>
            <p className="text-sm text-readout mb-4">
              This row&apos;s context window, checked against the provider&apos;s own catalog
              claim. Not a connectivity test — that is the provider card&apos;s Test.
            </p>

            <div className="space-y-3">
              <div className="text-sm">
                This row says{' '}
                <span className="font-mono">{verifyRow.contextLength ?? 'nothing'}</span>
                {verifyRow.verified
                  ? ' and is marked verified.'
                  : ' and is not marked verified.'}
              </div>

              {verifyError && (
                <div className="alert alert-error text-sm" role="alert">{verifyError}</div>
              )}

              {verifyResult && (
                <div className="bg-base-200 rounded-lg p-3 text-sm space-y-1">
                  <div>
                    <span className="text-readout">The row says now:</span>{' '}
                    <span className="font-mono">{verifyResult.window ?? 'nothing'}</span>
                    <span className="text-readout">
                      {' '}(it said {verifyResult.curated ?? 'nothing'})
                    </span>
                  </div>
                  <div>
                    <span className="text-readout">The provider&apos;s catalog says:</span>{' '}
                    <span className="font-mono">
                      {verifyResult.discovered ?? 'nothing for this model'}
                    </span>
                  </div>
                  <div>
                    <span className="text-readout">Read from:</span>{' '}
                    {verifyResult.refreshed ? 'a fresh provider fetch' : 'our recorded claim'}
                    {' '}· {claimAge(verifyResult.age_hours)}{verifyResult.stale ? ', past its TTL' : ''}
                  </div>
                  <div>
                    <span className="text-readout">The provider&apos;s reasoning claim:</span>{' '}
                    {verifyResult.thinking_provider ?? 'it says nothing'}
                    {verifyResult.thinking_adopted && (
                      <>{' '}— the row now says <span className="font-mono">{verifyResult.thinking_adopted}</span></>
                    )}
                  </div>
                  {verifyResult.max_completion != null && (
                    <div>
                      <span className="text-readout">The provider&apos;s own output cap:</span>{' '}
                      <span className="font-mono">{verifyResult.max_completion}</span>
                    </div>
                  )}
                  <div className={verifyResult.mismatch ? 'text-warning' : 'text-readout'}>
                    {verifyResult.mismatch
                      ? "The two numbers disagreed — the provider's won, and the row was adopted onto it."
                      : 'The numbers agreed, so nothing moved.'}
                  </div>
                  <div className="text-readout">{verifyResult.note}</div>
                </div>
              )}
            </div>

            <div className="modal-action">
              <button
                type="button"
                onClick={closeVerify}
                disabled={verifying}
                className="btn btn-ghost btn-sm"
              >
                Close
              </button>
              <span
                className="tooltip tooltip-top"
                data-tip="Read the claim our discovery fetch recorded. It may be dated — the result says how old."
              >
                <button
                  type="button"
                  onClick={() => runVerify(false)}
                  disabled={verifying}
                  className="btn btn-outline btn-sm"
                >
                  Read our own record
                </button>
              </span>
              <span
                className="tooltip tooltip-top"
                data-tip="Ask the provider for its model list again before comparing — one live request."
              >
                <button
                  type="button"
                  onClick={() => runVerify(true)}
                  disabled={verifying}
                  className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)]"
                >
                  {verifying ? 'Checking...' : 'Ask the provider again'}
                </button>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}