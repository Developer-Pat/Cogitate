---
title: Embedded Service Literals Index
type: atlas-index
path: wiki/issues/resolved/embedded-service-literals
category: issues
order: 1
confidence: high
created: 2026-10-12
updated: 2026-10-12
tags: [type/index, domain/issues]
---

# The embedded service literals — resolved

The pages the **embedded-service-literals** arc produced, kept as records rather than as a reading
list. Every one is RULED and LANDED (or measured and closed), and each keeps its evidence rows, its
figures, and the reason its losing options lost — the next reader is deciding one layer down, and the
measurement is the asset.

Arc context: the roadmaps are archived at `local/roadmaps/archive/embedded-service-literals/`, and the
session files that ran it are `local/sessions/`.

- [[issues/resolved/embedded-service-literals/local-embedding-server|The local embedding server]] —
  **LANDED — option C, both halves** (`3b3421fa`, `70369210`). One address and one model, written down
  12 times across the RAG layer, the three vector stores, chat and the provider layer.
- [[issues/resolved/embedded-service-literals/embedding-model-and-dims|The embedding model and its dimensions]] —
  **LANDED** (`e370818b`, `70369210`). `nomic-embed-text` and `768` written six times — the two halves
  of ONE fact held apart only by convention.
- [[issues/resolved/embedded-service-literals/ollama-cloud-two-api-roots|The Ollama Cloud row — one endpoint field, two API roots]] —
  **RULED — option A; LANDED** (`db0f05da`, `bb177a45`, `5669dee6`). One row field handed to two APIs
  that want different roots; the live bare value measured 404.
- [[issues/resolved/embedded-service-literals/agent-import-service|The agent import — a bundled config that names no service gets one written in code]] —
  **RULED — option A; LANDED** (`d019ba0e`), plus the workspace defect found while landing it
  (`34bd0500`).
- [[issues/resolved/embedded-service-literals/embedding-configuration-does-not-reach-a-running-process|The embedding configuration does not reach a running process]] —
  **RULED — options C then A; LANDED** (`3e7e067e`, `5508c9a7`). Filed by this arc's model-half landing
  and ruled later: the two vector stores captured the embedding service at first construction, so a
  model saved on the Capabilities page waited for a restart. C made the surfaces say what the process
  was doing (and the two stores refuse a width their index does not have); A made the change reach the
  process — the capability write resets the stores — and retired the restart sentence with it.

- [[issues/resolved/embedded-service-literals/duplicated-agent-partial-clone|A duplicated agent is a partial clone — 8 of 24 fields, and no workspace]] —
  **RULED — a copy is a scoped instance of the same character; LANDED** (`9fdf1435`). Found by the agent
  import's workspace fix (the same class) and re-measured live: the duplicate route hand-built 8 of
  `AgentCreate`'s 24 fields and called the row-only service path, so the copy had no key, no folder, no face,
  no skills and no tool surface at all. It now goes through the seam, and `domain/agents/clone.py` owns the
  field sort with the census test that keeps it honest.

- [[issues/resolved/embedded-service-literals/exa-model-save-undialable-provider|The Exa model save accepts a provider nothing can dial — and reports success]] —
  **RULED — option A, refuse the save; LANDED** (`458d8462`). The refusal half of the address page, given its
  own page because it is its own decision. Grounding it found the free-text provider field (so a typo reaches
  the path from the app's own surface) and a rejection reported as `200 {"error": …}` that the model card
  toasted as success. `provider_endpoints.address_for_client` now decides: explicit → the type's canonical →
  the row's own → clear → refuse.

- [[issues/resolved/embedded-service-literals/provider-addresses-registry-copies|The provider addresses — one registry, three copies, and a guard that only covers three types]] —
  **RULED — option A, staged; LANDED** (`458d8462`, `a7f41276`). Residue the arc filed rather than took. Two
  findings: the deepseek root question is answered, and not in the registry's favour (the vendor's docs and the
  live row both say the bare host; the registry's `/v1` was the one value nothing could point at), and the
  literal map covered 3 of the app's 7 provider types, so a save for any other left the PREVIOUS provider's
  address in Exa's config. The registry is now the one home, and the write refuses what nothing can dial.

- [[issues/resolved/embedded-service-literals/litellm-provider-mapping-four-homes|The litellm provider mapping — four homes for one decision, and two modules that skip it]] —
  **RULED — option A, one mapping in the DOMAIN (TYPE-keyed); LANDED in two stages** (`0f532be6` the string,
  `7990716a` the address). One decision — *which litellm string does this provider get, and which root does
  that handler need?* — was written in four places: the chat path's handler map, a two-entry alias table
  carrying a prefix AND an address, the endpoint registry, and two cognitive-pipeline modules that
  hand-rolled `{provider}/{model}` and so produced `ollama_cloud/<m>` / `llama/<m>` — strings litellm
  REJECTS. It has one home now (`domain/providers/litellm_route.py`: the handler from the row's TYPE, the
  root from the handler), the address rides the resolution that already holds the row, and the table is
  deleted.

**With this page the arc's residue is empty:** every item it filed is ruled and landed.
