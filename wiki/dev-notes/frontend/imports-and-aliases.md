---
title: Imports & the Path Alias
type: atlas-devnote
category: frontend
order: 13
confidence: verified
updated: 2026-10-13
tags: [type/dev-notes, domain/frontend]
---

# Imports & the Path Alias

How a frontend file names another one, why the alias exists, and the gate that enforces it.

## The alias

`@` → `frontend/src`, declared **once** in `frontend/aliases.ts` and imported by **both**
`vite.config.ts` and `vitest.config.ts`. One definition, because `vitest.config.ts` *shadows*
`vite.config.ts` (vitest prefers a dedicated config and does not merge), so an alias declared only in
the vite config resolved in the app and silently did not resolve under the test runner — the worst
version of a path bug. TypeScript learns the same mapping from `tsconfig.app.json`
(`"paths": { "@/*": ["./src/*"] }`).

## The rule

Name a module by the alias (`@/services/domain/ProfileService`), not by a hand-computed climb
(`../../../../services/domain/ProfileService`). A climb has to be re-counted every time a file
moves, and getting it wrong is a **runtime** failure rather than a compile error. A one-level climb
(`../types/x`) is local and fine.

Every specifier must **resolve**. That is the whole rule, and it covers cases the alias does not:

- **a test double is the dangerous one.** `vi.mock('../../services/x')` with a path that lands
  nowhere does not fail — **the mock silently applies nothing, the real module runs instead of the
  double, and the runner says nothing at all.** Four files did exactly this (three pointed at a
  doubled `services/services/`, one at `./TraceService` from inside `__tests__/`, a file that lives
  one level up). All four passed before and after the fix, which is why it went unnoticed.
- **`tsc` will not catch it for you** — the argument is a string, and the module graph it types
  through is the one that resolves.
- an aliased or relative specifier that names a **directory** resolves through its `index.ts`.

## The gate

`check_module_specifiers` in `scripts/core/sweep/frontend.py` — a pure-Python check (no shell-out),
registered first in `get_all_checks()` and run by the path-checks **pre-commit hook**
(`scripts/testing/precommit_path_checks.py`, alongside the backend's `check_path_arithmetic` and
`check_absolute_paths`). A commit that introduces a specifier which resolves to nothing is blocked,
with the file and line.

By hand:

```
python3 scripts/testing/precommit_path_checks.py      # all three path gates
```

It judges `import` / `export` / dynamic `import()` / the test-double calls (`vi.mock`, `jest.mock`
and friends); relative and aliased specifiers only (a bare name is a package — npm's question);
Vite's query suffixes (`?raw`, `?inline`) stripped; `.ts`/`.tsx`/`.js`/`.jsx`/`.mjs`/`.cjs`/`.json`/
`.css`/`.svg` and `index.ts` resolution. Its rules are pinned by
`backend/tests/unit/test_frontend_specifier_rules.py`, which also runs the check over the real tree
so the hook's gate and the suite's gate cannot disagree.

## The 2026-10-13 sweep

534 climbs across 216 files were converted to the alias in one mechanical pass, and the
four silent mocks were fixed after it. The sweep script was a one-shot
(`tmp/alias_sweep.py`, gitignored); the **gate** is what keeps the tree swept, and it asks the wider
question — *does it resolve?* — because the sweep's own rule (`(../){2,}`) could not see the fourth
mock at all.
