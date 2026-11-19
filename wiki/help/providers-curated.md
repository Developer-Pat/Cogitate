---
title: Curated Models
category: providers-curated
subtopic: Curated Model List
order: 1
confidence: high
created: 2026-08-03
tags: [domain/help]
---

# Curated Models

The curated model list is a **human-owned set of models** shown
when configuring an agent (ProfileDetail). It is separate from provider
model discovery:

- **Discovery** (`/providers/{id}/models/browse`) — machine-owned: live
  model lists fetched from each provider and cached.
- **Curation** (`curated_models` table) — human-owned: the models this
  system actually recommends. The DB is the source of truth; the
  `curatedModels.ts` config file is only a seed/fallback.

## Managing the list (this tab)

- **Add** — click "+ Add Model", pick provider (+ a category if you want
  one), enter the model ID exactly as the provider knows it (e.g.
  `nvidia/nemotron-3-super-120b-a12b:free`), a display name, and an
  optional description / context length. The **cost is not asked for**: it
  is read from the provider's own catalog as the row is created (see Cost).
- **Copy** — the clipboard icon copies the model ID exactly as the provider
  spells it. The ID column clips long ids; this takes the whole one, which is
  what an agent must be saved with.
- **Edit** — pencil icon; the model ID and provider are locked (they are
  the entry's identity), but name, category, description, context, and
  flags can change.
- **Read a note** — each row's description shows on the **name's tooltip**
  in the table: hover the model's name. That is where the note reads, so a
  row you have described can be reviewed without opening the edit form.
- **Delete** — trash icon; removes the model from recommendations. It
  does NOT affect the provider's actual model list (discovery).
- **Filter** — the dropdown above the table narrows it to one provider (`All`
  is the default, and each option says how many models it holds).

## Categories

A row's category is an **optional one-word note about what the model is FOR** —
leave it on "not described" if you have nothing to say. It is a label for
humans: nothing sorts or ranks by it. The cost fact is not a category — it is
the row's own **Cost** column, which reports what the provider's catalog says:

| Cost | Meaning |
|---|---|
| free | The catalog prices this model at zero |
| paid | The catalog charges for it |
| unpriced | The catalog states no price for this model |

Nothing sets the cost by hand: it is read off the provider's own cached
pricing when the row is created, and it is not accepted from the API.

| Category | Meaning |
|---|---|
| chat | The everyday conversational driver |
| code | Coding and tool work |
| reasoning | Hard, multi-step problems |
| vision | Takes images |

## Tips

- Model IDs must match what the provider actually serves — a stale ID
  will fail at chat time (visible via the agent health scan).
- **Verified ✓** is factual and **earned automatically** — a model is
  verified when a model sync (discovery/browse) confirms it exists in
  the provider's catalog. It is NOT user-settable: new entries start
  unverified and become verified on the next sync. It ages like any
  dependency pin — a model can churn or be unpulled later, which the
  agent health scan catches. Local-Ollama models that aren't currently
  installed stay unverified until pulled.
- `is_free` and `verified` drive the badges in agent setup. Display order
  is yours: press a column header to sort the table.
- Models with no matching provider (e.g. `groq (0)`) simply have no
  curated entries yet — add some or ignore.
