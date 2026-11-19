---
title: CapabilityEditModal
type: atlas-component
path: frontend/src/components/features/providers/CapabilityEditModal.tsx
confidence: high
updated: 2026-10-09
tags: [type/component, domain/atlas-ui]
---
# CapabilityEditModal

**Path**: `frontend/src/components/features/providers/CapabilityEditModal.tsx`

## Purpose

One capability's chain, edited in the house modal shell — **one capability per modal**. It holds the
editor that used to render INLINE, in place of the card's readout: an inline editor has to keep its
place in the same list that is showing the chains, so the thing being edited and the thing being
ordered competed for one row, inside a card about half the page wide. In the modal the readout stays
where it is, behind the shell, and each attempt gets a line of its own — so dismissing the editor
returns to exactly the list the reader was looking at.

The draft is seeded from the capability's **STORED** chain (`configured`), never from the resolution
(`primary`/`backups`): the resolution can be an agent's own declaration, expands a class candidate
into every row it matches, and leaves out rows switched OFF, so writing it back would silently
rewrite what the capability stores. Saving sends the **whole** chain and a candidate's position in
the list IS its ordinal. A refusal keeps the modal OPEN with the server's own sentence, so the
offending attempt can be fixed rather than the edit being lost.

## What an attempt row carries

The three ways an attempt can name its service — `provider_id` (a provider row), `require_location`
(rendered "Prefer a class"), `service_name` (a named engine/process) — plus the **model picker**, the
`thinking` level, the `Up`/`Down` reorder, `Remove`, and `Add a service`. The capability's own **Off**
switch rides the same write. The move/remove group is **right-aligned**, so when the row's controls
fill the line it wraps to a second line and still reads as that attempt's own controls rather than as
a new row.

`MoveButton` carries the disabled-control rule: a disabled button fires no hover, so its tip moves
onto a wrapper for exactly that state, where it says WHY ("Already first" / "Already last") rather
than repeating an action that cannot be taken.

## The model picker (`ModelField`)

An attempt's model is chosen from the **curated list for its provider** where one exists, so a model
name cannot be typed wrong; where the provider has no curated rows the field stays **free text**, as
it always was. The curated rows are keyed by provider NAME (`openrouter`, `ollama_cloud`, `llama`…)
while an attempt names its provider by ROW ID, so the row is resolved through the provider list
before the two are matched.

Three rules the picker must not break:

- **The option's VALUE is the model id, never the display name.** A curated row carries both (`id` is
  what the provider's API and the stored chain use; `name` is the human label). The agent-profile
  picker learned this the hard way — a display name saved there produced a model that does not exist.
- **A model the curated list does not carry stays selectable**, as its own option labelled
  `… (not in the curated list)`. Otherwise opening the editor and saving would silently replace it
  with the provider row's default.
- **The empty option is the provider row's own default** — what an empty `model` has always meant. The
  picker invents nothing.

The write is still the whole chain: `PUT /api/v1/providers/capabilities/{key}` via
`capabilitiesService` (`services/domains/providers/capabilitiesService.ts`), and a candidate's position
in the list IS its ordinal. A refusal keeps the modal OPEN with the server's own sentence, so the
offending attempt can be fixed rather than the edit being lost.

## Props

```typescript
interface CapabilityEditModalProps {
  capability: CapabilityReadout                     // the card's capability; `configured` seeds the draft
  providers: ProviderConfig[]                       // the provider picker's options
  providersError: string | null                     // a provider-list failure, shown without hiding the draft
  curated: CuratedModel[]                           // the curated lists the model picker reads
  curatedError: string | null                       // a curated-list failure; the model field falls back to free text
  onSaved: (updated: CapabilityReadout) => void     // the write's own answer
  onClose: () => void                               // every dismissal: Cancel, the close control, Escape, backdrop
}
```

Internal state is the draft's own: `rows` (`DraftRow[]`), `enabled`, `saving`, `saveError`. The page
holds only the read-out.

## Used by

[[atlas/ui/pages/ProviderCapabilities|ProviderCapabilities]] — the **Edit** action on a capability
card. The page keeps the mutated card in place from the response, and re-reads the whole read-out
when an agent is in the picker.

## Related

- [[atlas/ui/components/features/providers/ProviderModal|ProviderModal]] — the shell it renders in
  (`xl`, 1000px). Escape-to-close and focus containment come from it.
- [[atlas/ui/pages/ProviderCapabilities|ProviderCapabilities]] — the page and its read-out.
- `backend/app/api/v1/providers/capabilities_router.py` — `PUT /{key}`, the endpoint.
