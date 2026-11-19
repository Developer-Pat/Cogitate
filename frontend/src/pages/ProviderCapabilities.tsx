/**
 * PROVIDER CAPABILITIES (/providers/capabilities) — the service-capability arc, phase 6, group 2.
 *
 * One page answers the arc's exit criterion: **which service does each capability use, what are its
 * backups, and WHY that answer** — read from `GET /api/v1/providers/capabilities`, which resolves
 * every capability through the one resolver rather than describing the default row. The same page is
 * the EDIT path: each capability's chain can be changed, reordered, extended and switched OFF — in a
 * modal (`CapabilityEditModal`), one capability at a time, so the readout and the editor never
 * compete for the same row. An attempt's model is picked from the CURATED list for its provider where
 * one exists (so a model name cannot be typed wrong), and stays free text where it does not.
 *
 * ⚠️ TWO DIFFERENT CHAINS, and the page shows both on purpose:
 *
 * - the RESOLUTION (`primary`/`backups`) is what ANSWERS. It can come from an agent's own
 *   declaration, it expands a class candidate into every row that class matches, and it filters out
 *   rows switched off.
 * - the STORED chain (`configured`) is what this capability's rows SAY. That is what the editor
 *   reads and writes: sending the resolution back would drop a disabled row and rewrite expanded
 *   rows as if they were the ones stored.
 *
 * So the read-out is the sessionless view (no agent on the ladder), the editor edits what is stored,
 * and the page says which is which rather than pretending the two are one list.
 */

import { useCallback, useEffect, useState } from 'react'
import { PageBanner } from '../components/ui/PageBanner'
import { PageContainer } from '../components/ui/PageContainer'
import { HelpButton } from '../components/help'
import { usePageTitle } from '../hooks/usePageTitle'
import { useNotificationStore } from '../stores/notificationStore'
import { capabilitiesService } from '@/services/domains/providers/capabilitiesService'
import { providerConfigService } from '@/services/domains/providers/providerConfigService'
import { agentRosterService } from '@/services/domains/agents/agentRosterService'
import { fetchCuratedModels } from '@/services/domains/providers/curatedModelsService'
import CapabilityEditModal from '../components/features/providers/CapabilityEditModal'
import type { CapabilityCandidate, CapabilityReadout } from '@/types/capabilities'
import type { CuratedModel } from '@/config/curatedModels'
import type { AgentChoice } from '@/services/domains/agents/agentRosterService'
import type { ProviderConfig } from '@/types/providers'

/** The kinds, in the user's words. Keyed by the vocabulary so a new kind is a visible gap. */
const KIND_LABELS: Record<string, string> = {
  llm: 'LLM',
  speech: 'Speech',
  process: 'Process',
  embedding: 'Embedding',
}

const KIND_TIPS: Record<string, string> = {
  llm: 'A language model: a provider row answers',
  speech: 'A speech engine: piper, edge or whisper',
  process: 'An external process, such as the Exa agent',
  embedding: 'An embedding server and the model it runs — the vector index and search',
}

/** What each rung of the resolution ladder means, for the reason badge's tooltip. */
const REASON_TIPS: Record<string, string> = {
  'capability config': 'Chosen by this capability’s own configured chain',
  'global default': 'Nothing is configured for this capability, so the default provider row answers',
  'agent profile': 'Chosen by the agent’s own declaration',
  override: 'Chosen by an explicit per-request override',
  disabled: 'This capability is switched OFF — nothing resolves, and it never falls through',
  none: 'Nothing resolved: no candidate answered and no default provider row is set',
}

/** Why a capability with no primary shows nothing — keyed by the reason, never a ternary chain. */
const EMPTY_COPY: Record<string, string> = {
  disabled: 'Off — nothing resolves for this capability.',
  none: 'Nothing resolved: no candidate is configured and no default provider row is set.',
}

/**
 * The same copy, for a kind whose resolution does not work like an LLM's.
 *
 * An EMBEDDING capability never rides the default provider row — that rung is the install's CHAT
 * default, and the resolver skips it for this kind — so the generic 'none' line (which blames the
 * missing default row) would name a cause that cannot apply. This is the backend's own wording
 * (`domain/providers/embeddings.py::NO_EMBEDDING_MODEL`), so the card and the reports agree.
 */
const KIND_EMPTY_COPY: Record<string, Record<string, string>> = {
  embedding: {
    none: 'No embedding model is configured: indexing and search are off.',
  },
}

/** Only the rungs ABOVE the capability are worth naming on a candidate — a row's own source is obvious. */
const HIGHER_RUNG_SOURCES = new Set(['agent', 'override', 'default'])

/**
 * The availability read's own states, in this page's words. Keyed — never a ternary chain — so a
 * state with no entry falls through to nothing rather than to a wrong word, and `down-by-occupancy`
 * keeps its distinction from `down`: a swap-away is a CHOICE, not an incident.
 */
const AVAILABILITY_LABELS: Record<string, string> = {
  available: 'up',
  'down-by-occupancy': 'in use elsewhere',
  down: 'down',
  unconfigured: 'no key',
}

/** A short LOCAL time for a check stamp; the full ISO rides in the chip's own label. */
function checkedTime(iso: string): string {
  const at = new Date(iso)
  return Number.isNaN(at.getTime()) ? iso : at.toLocaleTimeString()
}

function candidateName(candidate: CapabilityCandidate): string {
  if (candidate.provider) {
    return candidate.model ? `${candidate.provider}/${candidate.model}` : candidate.provider
  }
  return candidate.service_name || '(unnamed)'
}

function CandidateRow({
  candidate,
  position,
}: {
  candidate: CapabilityCandidate
  /** The attempt's place in the RESOLVED chain: 0 is tried first, whatever the row was STORED as. */
  position: number
}) {
  const role = position === 0 ? 'primary' : `backup #${position}`
  // The stored ordinal and the resolved position disagree when a capability's own chain is the
  // BACKUP layer (the seeded `chat` has one candidate stored as a backup, and with no agent on the
  // ladder that row IS the first attempt). The order shown is the resolved one — it is what will be
  // tried — and the stored position is named beside it rather than silently contradicting it.
  const stored = candidate.ordinal === position ? '' : ` (stored #${candidate.ordinal + 1})`
  const details: string[] = []
  if (candidate.require_location) details.push(`prefer ${candidate.require_location}`)
  else if (candidate.location) details.push(candidate.location)
  if (candidate.thinking) details.push(`thinking ${candidate.thinking}`)

  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
      <span
        className="w-28 shrink-0 opacity-60"
        data-tip={position === 0 ? 'Tried first' : 'Tried if every attempt before it fails'}
      >
        {role}
        {stored}
      </span>
      <span
        className={position === 0 ? 'font-medium text-success' : 'font-medium'}
        data-tip={position === 0 ? 'The service that answers when nothing fails' : 'A backup, in the order it is tried'}
      >
        {candidateName(candidate)}
      </span>
      {/* WHAT THE ONE AVAILABILITY READ FOUND (group 5) — the STATE on the row, the read's own
          reason and WHEN it looked in the label. `unknown` draws nothing: "not checked" is not a
          state to paint, and a service nobody probed must not be made to look broken. */}
      {candidate.available === true && (
        <span
          className="badge badge-success badge-xs"
          data-tip={candidate.availability_reason || 'it answers'}
          aria-label={`Available — ${candidate.availability_reason || 'it answers'}${candidate.checked_at ? ` (checked ${candidate.checked_at})` : ''}`}
        >
          up
        </span>
      )}
      {candidate.available === false && (
        <span
          className="badge badge-error badge-xs"
          data-tip={candidate.availability_reason || 'it did not answer'}
          aria-label={`Not available — ${candidate.availability_reason || 'it did not answer'}${candidate.checked_at ? ` (checked ${candidate.checked_at})` : ''}`}
        >
          {AVAILABILITY_LABELS[candidate.availability_state || ''] || 'unavailable'}
        </span>
      )}
      {candidate.checked_at && (
        <span className="opacity-60">checked {checkedTime(candidate.checked_at)}</span>
      )}
      {details.length > 0 && <span className="opacity-60">{details.join(' · ')}</span>}
      {HIGHER_RUNG_SOURCES.has(candidate.source) && (
        <span className="opacity-60">
          (from the {candidate.source === 'agent' ? 'agent’s declaration' : candidate.source === 'override' ? 'request override' : 'default row'})
        </span>
      )}
    </div>
  )
}

function CapabilityCard({
  capability,
  providers,
  providersError,
  curated,
  curatedError,
  onSaved,
}: {
  capability: CapabilityReadout
  providers: ProviderConfig[]
  providersError: string | null
  curated: CuratedModel[]
  curatedError: string | null
  onSaved: (updated: CapabilityReadout) => void
}) {
  const [editing, setEditing] = useState(false)
  const title = capability.label || capability.key

  return (
    <section
      className={`card bg-base-100 shadow-md ${capability.enabled ? '' : 'opacity-60'}`}
      aria-label={title}
      data-capability={capability.key}
    >
      <div className="card-body gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="card-title text-sm">{title}</h2>
          <span
            className="badge badge-ghost badge-sm"
            data-tip={KIND_TIPS[capability.kind] || capability.kind}
          >
            {KIND_LABELS[capability.kind] || capability.kind}
          </span>
          <span
            className={`badge badge-sm ${capability.enabled ? 'badge-outline' : 'badge-error'}`}
            data-tip={REASON_TIPS[capability.reason] || 'The rung that answered'}
          >
            {capability.enabled ? capability.reason : 'disabled'}
          </span>
          {/* A READOUT, not a control: no tooltip (the house rule sends readouts to aria-label), but it
              needs an accessible name saying what the string IS, or it reads as a stray word. */}
          <span
            className="ml-auto font-mono text-[11px] opacity-60"
            aria-label={`Capability key: ${capability.key}`}
          >
            {capability.key}
          </span>
          {!editing && (
            <button
              type="button"
              className="btn btn-xs btn-outline"
              data-tip="Change which service this capability uses"
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
          )}
        </div>

        <div className="space-y-1 rounded-lg border border-base-300 p-2">
          {capability.primary ? (
            <CandidateRow candidate={capability.primary} position={0} />
          ) : (
            <p className="text-xs opacity-70">
              {KIND_EMPTY_COPY[capability.kind]?.[capability.reason] ||
                EMPTY_COPY[capability.reason] ||
                'No candidate to try.'}
            </p>
          )}
          {capability.backups.map((backup, index) => (
            <CandidateRow
              key={`${capability.key}-${backup.ordinal}-${index}`}
              candidate={backup}
              position={index + 1}
            />
          ))}
        </div>

        {/* THE EDIT RUNS IN A MODAL (one capability per modal). The readout above stays put, so
            dismissing the shell returns to exactly the list the reader was looking at — and the
            chain gets the room the half-width card could not give it. */}
        {editing && (
          <CapabilityEditModal
            capability={capability}
            providers={providers}
            providersError={providersError}
            curated={curated}
            curatedError={curatedError}
            onClose={() => setEditing(false)}
            onSaved={(updated) => {
              setEditing(false)
              onSaved(updated)
            }}
          />
        )}
      </div>
    </section>
  )
}

export default function ProviderCapabilities() {
  usePageTitle('Capabilities', 'Which service each part of the app uses, and its backups')
  const [readout, setReadout] = useState<CapabilityReadout[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState<ProviderConfig[]>([])
  const [providersError, setProvidersError] = useState<string | null>(null)
  const [curated, setCurated] = useState<CuratedModel[]>([])
  const [curatedError, setCuratedError] = useState<string | null>(null)
  const [agents, setAgents] = useState<AgentChoice[]>([])
  const [agentsError, setAgentsError] = useState<string | null>(null)
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await capabilitiesService.getCapabilities(selectedAgentId)
      setReadout(response.capabilities)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [selectedAgentId])

  // The editor's provider list — its own load, so a provider failure does not hide the read-out.
  const loadProviders = useCallback(async () => {
    try {
      const response = await providerConfigService.getProviders(true)
      setProviders(response.providers || [])
      setProvidersError(null)
    } catch (err) {
      setProvidersError(
        `Could not list the providers — ${err instanceof Error ? err.message : String(err)}`,
      )
    }
  }, [])

  // The editor's MODEL picker source — the curated lists, its own load like the provider list. A
  // failure here is not fatal: an attempt's model field simply stays free text.
  const loadCurated = useCallback(async () => {
    try {
      setCurated(await fetchCuratedModels())
      setCuratedError(null)
    } catch (err) {
      setCuratedError(
        `Could not list the curated models — ${err instanceof Error ? err.message : String(err)}`,
      )
    }
  }, [])

  // The agent picker's roster — its own load too, so a roster failure leaves the sessionless
  // read-out fully usable rather than blanking the page.
  const loadAgents = useCallback(async () => {
    try {
      setAgents(await agentRosterService.listAgents())
      setAgentsError(null)
    } catch (err) {
      setAgentsError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadProviders()
    void loadCurated()
    void loadAgents()
  }, [loadProviders, loadCurated, loadAgents])

  const handleSaved = (updated: CapabilityReadout) => {
    setReadout((current) =>
      current.map((row) => (row.key === updated.key ? updated : row)),
    )
    useNotificationStore
      .getState()
      .addSuccess(
        'Capabilities',
        selectedAgentId === null
          ? `${updated.label || updated.key} now resolves to ${updated.chain}`
          : `${updated.label || updated.key}’s chain was saved`,
      )
    // A SAVE THE INDEX CANNOT FOLLOW (2026-10-12): the write RESETS the RAG stores, so a saved model
    // reaches the process on its next use — but the index keeps the width it was CREATED at, and a
    // model of another width needs a re-ingest. The response carries that sentence; show it ALONGSIDE
    // the success toast rather than instead of it.
    if (updated.note) {
      useNotificationStore.getState().addWarning('Capabilities', updated.note)
    }
    // The save's own response carries the SESSIONLESS resolution; with an agent in view the read-out
    // must be re-asked, or the card would show a chain that disagrees with the picker.
    if (selectedAgentId !== null) void load()
  }

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? null

  return (
    <PageContainer>
      <PageBanner
        title="Capabilities"
        className="mb-6"
        action={<HelpButton context="providers-capabilities" size="sm" tooltipPosition="left" />}
        tooltip="What each part of the app uses, and what it would try if that fails"
      />

      {/* THE ORIENTATION (phase 7) — what the page is FOR, which the read-out alone does not say:
          what a capability is, that its chain is tried in ORDER, and the two reasons to configure one
          (the availability ruling's own: prefer a local engine, or have somewhere to fall back to). */}
      <p className="mb-4 text-xs opacity-60">
        A capability is a job the app needs done — answering chat, titling a session, speaking, hearing,
        running a workflow step. Each one uses the service you give it, and tries its chain in order: the
        first attempt that answers wins, and everything below it is a backup. Configure a chain to prefer
        a local engine, or to give a capability somewhere to fall back to when its service is down.
      </p>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="form-control">
          <span className="label-text text-xs opacity-60">Resolve for</span>
          <select
            className="select select-bordered select-sm w-64"
            value={selectedAgentId ?? ''}
            data-tip="Show what the capabilities resolve to for one agent — its own declared service is in play only where a live turn asks for it"
            aria-label="Resolve the capabilities for an agent"
            onChange={(e) => setSelectedAgentId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">No agent — each capability’s own chain</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </label>

        {selectedAgent && (
          <p className="pb-1 text-xs opacity-60">
            For {selectedAgent.name}: a capability a live turn runs on this agent shows the agent’s
            own declared service; every other card keeps its own answer.
          </p>
        )}
      </div>

      {agentsError && <p className="mb-3 text-xs text-error">{agentsError}</p>}

      {/* The picker's OWN note — the orientation above already said what a capability is, so this
          paragraph carries only what changes when an agent is in view. */}
      <p className="mb-4 text-xs opacity-60">
        An agent’s declaration is in play only where a live turn passes one — today that is the chat
        capability alone — so no card is shown a chain the capability would not use.
      </p>

      {error && (
        <div role="alert" className="alert alert-error mb-4 flex-wrap">
          <span className="text-sm">{error}</span>
          <button
            type="button"
            className="btn btn-xs"
            data-tip="Read the capabilities again"
            onClick={() => void load()}
          >
            Retry
          </button>
        </div>
      )}

      {loading && !readout.length && <p className="text-sm opacity-60">Reading the resolutions…</p>}

      {!loading && !error && readout.length === 0 && (
        <p className="text-sm opacity-60">No capabilities are configured.</p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {readout.map((capability) => (
          <CapabilityCard
            key={capability.key}
            capability={capability}
            providers={providers}
            providersError={providersError}
            curated={curated}
            curatedError={curatedError}
            onSaved={handleSaved}
          />
        ))}
      </div>
    </PageContainer>
  )
}
