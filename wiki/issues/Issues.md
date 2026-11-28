---
title: Issues
type: atlas-index
path: wiki/issues
category: issues
order: 1
confidence: high
created: 2026-10-10
updated: 2026-11-18
tags: [type/index, domain/issues]
---

# Issues

Problem records written to be READ WHILE WORKING: what is wrong, the evidence that shows it, the
options, and the ruling that closes it. A page here is meant to be open in a browser tab beside the
code, not filed away.

**This section is the wiki's sanctioned history surface.** Everywhere else is as-is — current state
only, no dates, no "it used to be". An issue is the opposite: it records what was measured, what was
tried, and what was decided, because the next reader hitting the same problem needs exactly that.
Its sibling surface is [[dev-notes/known-issues|Known Issues]].

## How a page is written

**A page is one decision thread** — one mechanism, one ruling. Several symptoms of one mechanism belong
on one page; a second mechanism, or a second ruling on the same one, gets its own. Name the problem in
the title, put **Status** first, then the evidence with `file:line`, then the options and the
recommendation. Diagrams are mermaid fences — the viewer renders them theme-aware. Draft in
`local/issues/`, land here.

**The folder is the status.** An open page — OPEN, or RULED and waiting to land — sits at the top of this
section. A resolved one (the ruling landed, or measured and closed as not-a-defect) moves to
`resolved/<arc>/`, grouped by the arc that produced it, the same arc key a roadmap archive uses. Resolved
pages stay readable and indexed; they do not accumulate in the working folder.

**A page is written for the decision in front of us.** The queue is a local backlog, one item
per pending ruling with its measurement; a page is spent when we take one up. Several open pages at
once is a sign the previous arc was cut one step early.

**One home per status.** This index carries each page's status and is the ONLY place it is repeated —
the Site Index links this section, never its pages.

## In flight

- [[issues/embedding-model-three-facts-one-transport|The embedding model — three facts, one accepted transport, and a choice the install hands to you]] —
  **OPEN — needs a ruling.** An install with no embedding model reports `no embedding model: indexing and
  search are off` (measured: **0** documents, 0 bytes), while a working one holds **506 documents / 3,527
  chunks** at width **768** *and* reports `embedding_model: null` — the index outliving the configuration that
  built it. The three facts live in three homes (the candidate's row for the address, the candidate for the
  model, a **ten-entry** width table for the width), and a model outside that table is **reported, never
  guessed**. The transport narrows the choice more than the provider list suggests: the app speaks Ollama's
  `/api/embeddings` and `/api/embed` at three call sites and `/v1/embeddings` **nowhere**, so a llama.cpp
  server (which serves `/v1/embeddings` only) and the hosted vendors are a small client this app does not
  have. Recommendation: **A now** — ollama and `nomic-embed-text` (768, 261.6 MB) on the box, keyless — and
  **C as its own item** — the `/v1/embeddings` client, which unlocks this box's llama.cpp and every hosted
  vendor at once.

- [[issues/seven-levers-one-stable-reading|Seven parked levers, and the set holds one stable reading for them]] —
  **OPEN — needs a ruling.** The reporter arc parked seven levers; the bench holds 3 jobs over **2** of the
  charter's six axes, and the levers land on the four axes with no job. Measured against the instrument's own
  band: the set prices **one** lever outright (the brief — a 15 % band), **one** as a ceiling (verification,
  `rounds` swings 3× on an unchanged job), **one** on half its effect (detail levels — the cost half rides the
  only 0 %-spread quantity, the coverage half is untested), and **four** not at all. The lever step 4's plan
  proposes — the cap's size — is not on the list: it landed (`fab3f6b3`) and no fixture's fact sits past a
  6.4 K head window. Recommendation: **B, staged** — write the free `churn`-axis job, land detail levels, read
  one announced run of four jobs.

## Resolved

- [[issues/resolved/ci-gate/seven-ways-the-ci-gate-lied|Seven ways the CI gate lied — the green tick, the cancelled check, and the test that measured the developer]] —
  **CLOSED — five of the seven landed; two banked** *(an IRR: the report over one arc's CI failures, not one
  mechanism)*. Eighteen pushes to `main` in six days returned **5 green, 5 red and 8 cancelled**, and none of the
  words was a verdict about the code: `frontend` ran no linter while #19 merged a rule change behind its green
  tick; `cancelled` covered a superseded push, a job killed at its own 30-minute cap (**6** kills, the worst run
  **138.4 minutes**) and a stall that reported nothing — and the same job outcome reached the page as `failure`
  twice because the *frontend* job failed first. A red job's whole log was `EXIT 1`; the seven failure names lived
  in the artifact. Landed: the per-test cap that named the hang (`71f4bea`, `47a6c59`), the machine-dependent
  refusal stubbed at the seam the code calls (`591ebb0`, `4c9f7e8`, `f94516f`), the millisecond timestamp that was
  a real bug and not a flake (`bf793e2`), and the bump-is-a-migration rule (#16's **142** findings, #24's fastapi
  `_IncludedRouter` and its **7** failing observers). Banked, and named on the page: the lint step itself, and the
  runner printing no failure name to stdout.

- [[issues/resolved/github-release/the-check-reads-its-own-process-path|The check reads its own process's PATH — one install, two verdicts, and two capabilities that vanish]] —
  **LANDED — `46845da`** *(ruled 2026-11-21: "let'sgo with C", stage A; stage B measured and not taken)*. The app
  resolves two binaries by name — `hermes` (Exa's runtime) and `edge-tts` (speech) — and both live in
  `~/.local/bin`, which never reached the backend: `cogitate.sh:251-259` launched uvicorn with
  `setsid env -u CORS_ORIGINS …` and no PATH term, so the process inherited its starter's. Measured on ONE
  clone at `a3e1ccc`: after `restart` from a login terminal the readiness check read Exa's runtime **`ok`**;
  after `restart` over an SSH non-login shell the same files read **`optional`** — *"'hermes' is not on PATH"* —
  and that process could not spawn Exa at all, since the spawn gate is the same `shutil.which`
  (`services.py:860`). `ready` never moved (`counted: false`), which is why the headline number was silent.
  **A** — the launch line sets `PATH="$HOME/.local/bin:$PATH"` — proven A/B/A on the frozen guest: `optional`,
  the term, `ok`, the revert, `optional`. **B** (an in-process resolver, so a start that bypasses
  `cogitate.sh` is honest too) measured and not taken: 0 docs mention PATH and 0 tests touch the launcher.

- [[issues/resolved/github-release/one-turn-answers-twice|One turn answers twice — the server replaces the answer, and the wire never says so]] —
  **LANDED — `3737198`** *(ruled 2026-11-20: "let's go with A+B", and "brevity never earns a call")*. Measured:
  *"Bob, one word: ready?"* was answered `Ready.`, the conduit routed HYBRID on **brevity alone**
  (`content_len=6`, six of the eight profiles are `hybrid`), and a second **6,086-token** prompt answered
  `Ready.` again — the bubble read `Ready.Ready.` while the saved row held `Ready.`, because the server
  REPLACES the answer at four sites and the wire never said so. **A**: a lazy `delta.replace` frame before
  every superseding pass's first content chunk, the client resetting its accumulator (a pass that writes
  nothing clears nothing, so the empty-deep case needs no re-send). **B**: `is_short` is gone — a short answer
  that answers is a complete answer; intent (`DEEP_KEYWORDS`) or an answer cut at the output budget
  (`finish_reason == "length"`) earns the second call. The same class sat on the main loop's rounds, so a
  tool turn's narration now clears when its answer arrives. Control run: disabling the frame fails exactly
  the three supersede tests, one of which reproduces `Blue.Blue.`.

- [[issues/resolved/github-release/example-env-file-vs-the-config-surface|The example environment file names 30 keys against a surface of 50]] —
  **LANDED — `a77ea63e`** *(ruled 2026-11-18: "let's go with C")*. The app reads **50** environment keys (42
  `Settings` fields, all defaulted, plus 8 reads that bypass `Settings`); the shipped `.env.example` named
  **30**, of which **22** landed on a key something reads and **8 were dead or misspelled** — including
  `LANGFUSE_TRACING_ENVIRONMENT`, which the app does not read, while `LANGFUSE_ENVIRONMENT`, which it does, was
  absent (measured: the documented name yielded `''`, the real one `'production'`). **26 keys the app reads were
  named nowhere**, the README promised "a complete list … including … encryption configuration" while
  `COGITATE_ENCRYPTION_KEY` was in none of the three files, and **no check existed**. **C, staged**: the dead
  names and the over-claim went first, then `.env.example` became generated from `Settings` by
  `scripts/dev/generate_env_example.py`, `--check`ed in the pre-commit hook and the flat-tree gates. The landing
  exposed a **second defect in the same seam** — `Settings` resolved `.env` against the cwd, so configuration
  actually arrived through litellm's import-time `load_dotenv()`; now anchored to `BASE_DIR`.

- [[issues/resolved/github-release/script-catalog-check-no-cadence|A generated catalog, a checker with no cadence, and a stamp that would fail it every day]] —
  **LANDED — `ee422bfa`** *(ruled 2026-11-18)*. `wiki/docs/script-catalog.md` is generated and its `--check` is
  correct — 0.79 s, exit 1, and it catches a one-word docstring edit — but **nothing called it**: no hook,
  sweep, test or structural gate. On a clean tree it was already stale again, and the whole diff was one line,
  because the builder stamps `updated: date.today()` (`generate_script_catalog.py:198`). **C, staged**: the
  comparison normalises that one line (deriving the stamp from git breaks in the flattened tree the gate exists
  to clear), the check runs as a pre-commit hook, and `verify_flat_tree.sh` gains the row. The rejected options
  stay on the page with why they lost.

- [[issues/resolved/github-release/atlas-phase1-gate-cannot-run|The atlas Phase-1 gate cannot run, and the claim it made has no heir]] —
  **LANDED — `7fc54da2`** *(ruled 2026-11-18)*. `scripts/core/check_atlas_phase1.py` hardcoded
  `~/Projects/cogitate/wiki/ui-atlas/pages`, a directory that stopped existing when the atlas moved, so it died
  with `FileNotFoundError` before checking anything (**measured**); nothing called it and no test named it. Its
  stale-name half is genuinely covered (`check_atlas_validation.py:34-41` carries the same six patterns, run by
  the sweep, the flat-tree gates and a test); its coverage half — does every page have a doc, is any doc a stub
  — has no owner, and the tree moved under its hardcoded 28-name list (2 names gone, 21 docs unlisted). The
  page went; the coverage claim is filed as its own `needs-defining` item.

- [[issues/resolved/availability-bridge/is-this-provider-up|"Is this provider up?" — five answers, one channel, and no bridge]] —
  **LANDED, all four seams** *(the user's rulings, 2026-10-14)*: the app answers *"can this provider
  answer right now?"* in **five** unconnected places (the probe memo, a failure-count monitor nothing
  feeds, a 30-second browser poll that mis-reads it, a browser gate that keys off the resulting
  `undefined`, the sweep's config-only provider check) while the channel that reaches the user —
  `publish_warning` → SSE → every open tab — published only *after* a turn had already failed. The
  bridge built the missing one, in four seams: **which end failed** (`b25b3f17` — the probe names the
  class instead of collapsing every failure into *"the provider did not answer"*), **a connection verdict
  DERIVED from calls the app already makes** (`f459cedf` — one answered call proves the path works, while
  blaming the connection takes two distinct destinations silent the same way), **a state CHANGE as news**
  (`099eea87` — one rule, three producers; the first sight of a problem speaks, and a cloud failure under
  a dead connection is the network's story rather than the provider's), and **the idle poll**
  (`9ee70c74` — this machine's own rows, loopback only, so a timer puts no packet on anybody's network).
  The constraint that shaped the whole thing is the user's: the app may run on **somebody else's
  network**, so the bridge adds **zero network access of its own**, and while idle it sends **nothing that
  leaves the machine** — *"we notify when WE have a problem. We don't go looking for them."* The page also
  records the five answers it did **not** fix (the monitor trio and the sweep's config-only check are
  filed, not deleted) and the two leads its own work raised.

- [[issues/resolved/input-budget/next-focus-selection|The next focus — two lists that disagree, and three candidate premises that did not survive measurement]] —
  **RULED — the next arc is THE INPUT BUDGET** *(the user's words, 2026-10-12)*: what the app accounts for
  against what it actually sends. The selection itself was IRW'd — nine candidates measured, three premises
  falsified (the deep agents' memory chain IS wired; the path-locator sweep has **2 hits left in one file**;
  *"seed the LLM Wiki"* describes a corpus that already exists) — and four of the project's six stated
  priorities have no item at all. The arc opens on the finding that the budget counts each history message's
  `content` alone while the **tool schemas**, the **replayed `reasoning_content`** and the **in-turn tool
  results** ride along uncounted: measured at **35K–65K** tokens against a 12,800 threshold and a 16,000
  ceiling. Nothing has been decided beyond the focus — the roadmap is the arc's first work.
- [[issues/resolved/embedded-service-literals/Embedded Service Literals Index|The embedded service literals arc]] —
  **9 pages, all ruled and landed**: the embedding family's address half and model half, the `ollama_cloud`
  row's two API roots, the agent import's service, the two this arc's own landings filed — the embedding
  configuration that did not reach a running process (`3e7e067e`, `5508c9a7`) and a duplicated agent that was
  a partial clone (`9fdf1435`) — the provider addresses, refused and de-duplicated in two landings
  (`458d8462`, `a7f41276`), and the litellm provider mapping, given one home in two stages (`0f532be6`,
  `7990716a`), all on 2026-10-12.
