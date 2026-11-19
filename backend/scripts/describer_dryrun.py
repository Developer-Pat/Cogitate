"""The describer DRY RUN — generate a line per test module, judge it blind, compare.

WHAT IT IS NOT: it writes nothing into the 174 test files and nothing on the page.
Its output is evidence — a JSONL manifest plus a summary — so the decision to
change any description is taken on data, by the user.

THE TWO HALVES, and why the second one is the whole point:

  GENERATE  the house chain (free route -> the local Bonsai -> deepseek) gets the
            module's source and writes ONE line: what the tests check, present
            tense, <=95 chars, no dates/phases/codenames.
  JUDGE     a second call gets the SOURCE plus the module's CURRENT description and
            the GENERATED one, and says which is better. It runs on a DIFFERENT
            model family (deepseek direct) so the generator does not grade its own
            homework, the A/B order is RANDOMISED, and the provenance is never
            mentioned — it is not told which line the app already ships.

THE GATE, before this is pointed at all 174 (the user's rule: be told before a live
trickle test): run a handful of modules first and read the per-call SECONDS off the
manifest. Per-call latency is the one unmeasured number and it decides whether the
full run is half an hour or four hours.

THE CALIBRATION, before the judge's verdicts are believed: include the two modules
whose CURRENT descriptions are known to be FALSE (`workflows/test_routing.py`,
`unit/test_agent_beats.py`). If the judge cannot pick the true line over the false
one where we already know the answer, its verdicts on the other 169 are decoration.

RUN IT FROM THE REPO ROOT. `settings` resolves its `.env` against the CURRENT
DIRECTORY, so running from `backend/` silently loads no keys: the cloud steps fail
instantly and every call is served by the local model. The startup report says
which steps are reachable, so this cannot pass unnoticed.

    uv run python backend/scripts/describer_dryrun.py --offline      # prompts only, no calls
    .venv/bin/python3 backend/scripts/describer_dryrun.py --select timing --no-judge
    .venv/bin/python3 backend/scripts/describer_dryrun.py --select calibration
    .venv/bin/python3 backend/scripts/describer_dryrun.py                # all 174, resumable
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.pseudo_agents.catalog import TAG_WORKER  # noqa: E402
from app.domain.pseudo_agents.spec import (  # noqa: E402
    ChainStep,
    PseudoAgentError,
    PseudoAgentSpec,
    invoke,
)
from app.domain.testing.catalog import build_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "backend" / "tests"
MANIFEST = ROOT / "local" / "describer-dryrun.jsonl"
DEEPSEEK_URL = "https://api.deepseek.com"

DESCRIBER_SYSTEM = (
    "You describe Python test modules. Given the source of a test file, write ONE "
    "COMPLETE SENTENCE saying what the tests CHECK - the properties they assert, not "
    "which module they live in. Present tense. No dates, no phase or session numbers, "
    "no project codenames. At most 95 characters INCLUDING the final full stop. "
    "Return ONLY the sentence, with no quotes and no prose."
)

JUDGE_SYSTEM = (
    "You compare two descriptions of a Python test module. You are given the module's "
    "source and two candidate one-line descriptions, A and B, in no particular order. "
    "Decide which better describes WHAT THE TESTS CHECK - favour the specific and the "
    "accurate, and treat a claim the tests do not support as a defect. "
    'Reply ONLY with JSON: {"winner": "A" or "B" or "equal", "why": "at most 15 words"}.'
)

# THE GENERATOR: the module's own chain, so the dry run measures the thing the
# workflow would actually use. Source is NOT truncated - the largest module is
# 29,903 chars (~7.5K tokens) against a 262K context, so the probe's 6K cap had no
# basis and would have handicapped the worker on 36% of the corpus.
GENERATOR = PseudoAgentSpec(
    name="describer-dryrun",
    system_prompt=DESCRIBER_SYSTEM,
    chain=TAG_WORKER.chain,
    temperature=0.0,
    max_tokens=4000,
)

# THE ARMS — pinned single-step chains, for the online-vs-local comparison.
# PINNING IS WHAT MAKES THE COMPARISON POSSIBLE AT ALL: the house chain SUBSTITUTES
# silently, so one module yields exactly one line and the other provider's answer is
# never produced. Pinned, a provider that answers with nothing is DATA (its usable
# rate), not a silent substitution.
FREE_STEP = TAG_WORKER.chain[0]
LOCAL_STEP = TAG_WORKER.chain[1]
DEEPSEEK_STEP = TAG_WORKER.chain[2]


def _pinned(arm: str, step: ChainStep, max_tokens: int) -> PseudoAgentSpec:
    return PseudoAgentSpec(
        name=f"describer-{arm}",
        system_prompt=DESCRIBER_SYSTEM,
        chain=(step,),
        temperature=0.0,
        max_tokens=max_tokens,
    )


ARMS: dict[str, PseudoAgentSpec] = {
    "free4k": _pinned("free4k", FREE_STEP, 4000),      # the free route as configured today
    "free16k": _pinned("free16k", FREE_STEP, 16000),   # ... with room to finish thinking
    "free32k": _pinned("free32k", FREE_STEP, 32000),   # ... and with a lot more room
    "local": _pinned("local", LOCAL_STEP, 4000),       # the Bonsai, pinned
    "chain": GENERATOR,                                # the fallback order = the workflow's path
}

# THE JUDGE: one step, deepseek direct - a DIFFERENT family from the free route the
# generator prefers, which is the cheapest available way to blunt self-preference.
JUDGE = PseudoAgentSpec(
    name="describer-judge",
    system_prompt=JUDGE_SYSTEM,
    chain=(
        ChainStep(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url=DEEPSEEK_URL,
            has_api_key=True,
            api_key_setting="deepseek_api_key",
        ),
    ),
    temperature=0.0,
    max_tokens=4000,
)


def source_of(rel: str) -> str:
    return (TESTS / rel).read_text(encoding="utf-8")


def existing_line(rel: str) -> str:
    """The description the page renders: the first non-blank line of the module docstring."""
    text = source_of(rel)
    m = re.search(r'"""(.*?)"""', text, re.DOTALL) or re.search(r"'''(.*?)'''", text, re.DOTALL)
    if not m:
        return "(none)"
    for line in m.group(1).strip().splitlines():
        if line.strip():
            return line.strip()
    return "(empty)"


def clean(raw: str) -> str:
    line = raw.strip().strip('"').strip("'").strip()
    return line.splitlines()[0][:120] if line else ""


def generate(rel: str) -> dict:
    prompt = f"Describe this test module.\n\n```python\n{source_of(rel)}\n```"
    t0 = time.monotonic()
    try:
        res = invoke(GENERATOR, prompt)
        return {
            "text": clean(res.text),
            "served_by": res.served_by,
            "seconds": round(time.monotonic() - t0, 2),
            "degraded": res.degraded,
            "error": None,
            # THE PROVENANCE, kept per row: which steps failed, why, and how long each
            # took. Without it a run cannot say how often the free route empties out -
            # the whole reason the chain fell through today, and the number that decides
            # whether the free route is worth keeping in the chain at all.
            "attempts": res.attempts,
        }
    except PseudoAgentError as exc:
        return {
            "text": "",
            "served_by": "-",
            "seconds": round(time.monotonic() - t0, 2),
            "degraded": True,
            "error": str(exc)[:300],
            "attempts": [],
        }


def judge(rel: str, current: str, generated: str, rng: random.Random) -> dict:
    """Blind A/B. Returns the verdict ALREADY mapped back to current/generated."""
    generated_first = rng.random() < 0.5
    a_text, b_text = (generated, current) if generated_first else (current, generated)
    a_is = "generated" if generated_first else "current"

    prompt = (
        f"Describe this test module.\n\n```python\n{source_of(rel)}\n```\n\n"
        f"Candidate A: {a_text!r}\n"
        f"Candidate B: {b_text!r}\n"
    )
    t0 = time.monotonic()
    try:
        res = invoke(JUDGE, prompt)
        raw = res.text
        served_by = res.served_by
    except PseudoAgentError as exc:
        return {"verdict": "unjudged", "winner_raw": None, "why": str(exc)[:200],
                "a_is": a_is, "served_by": "-", "seconds": round(time.monotonic() - t0, 2)}

    winner, why = _parse_verdict(raw)
    if winner == "A":
        verdict = a_is
    elif winner == "B":
        verdict = "current" if a_is == "generated" else "generated"
    else:
        verdict = "equal"
    return {"verdict": verdict, "winner_raw": winner, "why": why, "a_is": a_is,
            "served_by": served_by, "seconds": round(time.monotonic() - t0, 2)}


def judge_between(rel: str, left: str, right: str, left_name: str, right_name: str,
                  rng: random.Random) -> dict:
    """A blind A/B between two candidate lines, returned already mapped to NAMES.

    The names are never shown to the judge: it sees "Candidate A" and "Candidate B" and
    the order is randomised per call, so neither position nor wording hints at which
    side is the app's shipped line and which is the arm under test.
    """
    left_first = rng.random() < 0.5
    a_text, b_text = (left, right) if left_first else (right, left)
    a_name = left_name if left_first else right_name
    b_name = right_name if left_first else left_name

    prompt = (
        f"Describe this test module.\n\n```python\n{source_of(rel)}\n```\n\n"
        f"Candidate A: {a_text!r}\n"
        f"Candidate B: {b_text!r}\n"
    )
    t0 = time.monotonic()
    try:
        res = invoke(JUDGE, prompt)
        winner_raw, why = _parse_verdict(res.text)
        served_by = res.served_by
    except PseudoAgentError as exc:
        winner_raw, why, served_by = None, str(exc)[:200], "-"

    if winner_raw == "A":
        winner = a_name
    elif winner_raw == "B":
        winner = b_name
    else:
        winner = "equal"
    return {"winner": winner, "winner_raw": winner_raw, "why": why,
            "a_was": a_name, "served_by": served_by,
            "seconds": round(time.monotonic() - t0, 2)}


def _parse_verdict(raw: str) -> tuple[str | None, str]:
    """The judge is asked for JSON; read it, and fall back to the letters if it rambles."""
    blob = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if blob:
        try:
            data = json.loads(blob.group(0))
            w = str(data.get("winner", "")).strip().upper()
            if w in {"A", "B"}:
                return w, str(data.get("why", ""))[:120]
            if w:
                return "equal", str(data.get("why", ""))[:120]
        except json.JSONDecodeError:
            pass
    text = (raw or "").lower()
    if "equal" in text or "equivalent" in text or "tie" in text:
        return "equal", text[:120]
    m = re.search(r"winner\"?\s*[:\-]?\s*\"?([ab])\b", text)
    if m:
        return m.group(1).upper(), text[:120]
    return None, text[:120]


def select_modules(which: str, limit: int | None) -> list[str]:
    """`timing` = five across the size range; `calibration` = the known-false pair plus peers."""
    catalog = build_catalog()
    rels = [r["path"] for r in catalog["tests"]]
    sized = sorted(rels, key=lambda r: (TESTS / r).stat().st_size)

    if which == "sample":
        rows = [
            "workflows/test_routing.py",
            "unit/test_agent_beats.py",
            "unit/tools/test_jina_reader_guard.py",
            "unit/cognitive_pipeline/test_conversation_compactor.py",
            "workflows/test_trigger_scheduler.py",
        ]
    elif which == "timing":
        picks = [0, len(sized) // 4, len(sized) // 2, (3 * len(sized)) // 4, len(sized) - 1]
        rows = [sized[i] for i in picks]
    elif which == "arms30":
        # A STRATIFIED SAMPLE, plus the modules the CALIBRATION needs. Stratified because
        # the question is whether the arms differ, and the arms differ most on the long
        # files; the forced six are the ones whose current description we can independently
        # judge (two KNOWN FALSE, four known-specific), which is what calibrates the judge.
        forced = [
            "workflows/test_routing.py",              # KNOWN FALSE current description
            "unit/test_agent_beats.py",               # KNOWN FALSE current description
            "unit/tools/test_jina_reader_guard.py",
            "workflows/test_trigger_scheduler.py",
            "unit/test_catalog_checker.py",
            "unit/test_pseudo_agent_chain.py",
        ]
        third = len(sized) // 3
        rows = forced + [r for r in sized[:third][:10]
                         if r not in forced] + [r for r in sized[third:2 * third][:10]
                                                if r not in forced] + [r for r in sized[2 * third:][-10:]
                                                                       if r not in forced]
    elif which == "calibration":
        # THE TWO KNOWN-FALSE descriptions, plus the three the sweep already fixed
        # (a known-specific line) - the judge must prefer truth on the first pair and
        # be able to call a tie on the rest.
        rows = [
            "workflows/test_routing.py",
            "unit/test_agent_beats.py",
            "unit/tools/test_jina_reader_guard.py",
            "workflows/test_trigger_scheduler.py",
            "unit/cognitive_pipeline/test_conversation_compactor.py",
            "unit/test_agent_selection.py",
            "unit/cognitive_pipeline/test_reasoning_support.py",
            "unit/cognitive_pipeline/test_context_builder.py",
            "unit/test_catalog_checker.py",
            "unit/test_pseudo_agent_chain.py",
        ]
    else:
        rows = rels

    # A MISSING PATH IS SAID OUT LOUD. The first draft of the calibration list had two
    # typos, and the silent filter below turned a 10-module calibration into an
    # 8-module one without a word - the calibration is the step that decides whether
    # the judge can be believed, so a quiet shrink of it is the worst possible silence.
    missing = [r for r in rows if not (TESTS / r).exists()]
    for rel in missing:
        print(f"  WARNING: {rel} is not in the test tree - dropped from the selection", flush=True)
    rows = [r for r in rows if (TESTS / r).exists()]
    return rows[:limit] if limit else rows


def _display(path: Path) -> str:
    """Repo-relative when it is inside the repo, absolute otherwise (a manifest may be given)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def done_paths() -> set[tuple[str, str]]:
    """(path, arm) pairs already in the manifest.

    THE ARM IS PART OF THE KEY, and leaving it out is a data-destroying bug: with two
    arms writing to one manifest, a resume that keyed on the path alone would skip every
    module the FIRST arm had already done, so the second arm's rows would never be
    written and the gap would look like modules the arm had failed on.
    """
    if not MANIFEST.exists():
        return set()
    done: set[tuple[str, str]] = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
            done.add((d["path"], d.get("arm", "chain")))
        except (json.JSONDecodeError, KeyError):
            continue
    return done


def environment_report() -> None:
    """SAY WHAT IS REACHABLE BEFORE SPENDING CALLS — the first gate run measured the wrong thing.

    `settings` resolves its `env_file` (".env") against the CURRENT WORKING DIRECTORY. Run
    this from `backend/` and no keys load, so the chain's cloud steps fail instantly and every
    call is served by the local Bonsai — a real result, but not the one being asked for. The
    local step also fires with an EMPTY model id (the documented `llama_model_path` defect)
    and llama.cpp answers anyway because it ignores the name. Both facts are printed here so
    a run can never again be mistaken for the chain's normal path.
    """
    from app.core.config import get_settings

    s = get_settings()
    or_key = bool(getattr(s, "openrouter_api_key", None))
    ds_key = bool(getattr(s, "deepseek_api_key", None))
    llama = (getattr(s, "llama_model_path", None) or "").strip()
    print(f"  step 1 openrouter free : {'key visible' if or_key else 'NO KEY VISIBLE'}")
    print(f"  step 2 local Bonsai    : {'model ' + Path(llama).name if llama else 'model path EMPTY (the known defect)'}")
    print(f"  step 3 deepseek direct : {'key visible' if ds_key else 'NO KEY VISIBLE'}")
    if not (or_key or ds_key):
        print("  ⚠️  NO CLOUD KEY VISIBLE — every call will be served by the LOCAL model.")
        print("     settings' env_file is '.env', resolved against the CWD: run from the REPO ROOT.")


def run_judge_compare(args, out: Path) -> int:
    """Judge two arms against each other, blind, on the modules where BOTH answered.

    THE DENOMINATOR IS THE POINT. An arm that answers rarely only gets compared on the
    modules it CHOSE to answer, which flatters it — so the count of skipped modules is
    printed as prominently as the verdicts, and a winner is never reported without the
    number of modules the comparison actually ran on.
    """
    pair = [s.strip() for s in args.judge_compare.split(",")]
    if len(pair) != 2:
        print("  --judge-compare wants TWO names, e.g. free16k,local")
        return 2
    left_name, right_name = pair
    arms_manifest = Path(args.arms_manifest)
    rows = ([json.loads(line) for line in arms_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
            if arms_manifest.exists() else [])
    by_path: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_path.setdefault(r["path"], {})[r.get("arm", "chain")] = r

    already = set()
    if args.resume and out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                already.add((d["path"], tuple(d.get("pair", []))))
            except (json.JSONDecodeError, KeyError):
                continue

    def line_for(rel: str, name: str, arms: dict[str, dict]) -> str:
        if name == "current":
            return existing_line(rel)
        return (arms.get(name) or {}).get("generated", "")

    rng = random.Random(args.seed + 1)
    judged = skipped = 0
    tally = {"left": 0, "right": 0, "equal": 0, "unparsed": 0}
    for i, (rel, arms) in enumerate(sorted(by_path.items()), start=1):
        if (rel, tuple(pair)) in already:
            continue
        left = line_for(rel, left_name, arms)
        right = line_for(rel, right_name, arms)
        if not left.strip() or not right.strip():
            skipped += 1
            print(f"  [{i}/{len(by_path)}] {rel} - SKIPPED ({left_name}="
                  f"{'yes' if left.strip() else 'EMPTY'}, {right_name}="
                  f"{'yes' if right.strip() else 'EMPTY'})", flush=True)
            continue
        res = judge_between(rel, left, right, left_name, right_name, rng)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"path": rel, "pair": pair, "left": left, "right": right, **res}) + "\n")
        judged += 1
        key = ("unparsed" if res["winner_raw"] is None
               else "left" if res["winner"] == left_name
               else "right" if res["winner"] == right_name else "equal")
        tally[key] += 1
        print(f"  [{i}/{len(by_path)}] {rel}  {res['seconds']}s  winner={res['winner']}  "
              f"({res['why'][:50]})", flush=True)

    print(f"\n  pair {left_name} vs {right_name}: judged {judged}, SKIPPED {skipped} "
          f"(a skip = one side produced nothing, so there was nothing to compare)")
    for key, label in (("left", left_name), ("right", right_name), ("equal", "equal"), ("unparsed", "UNPARSED")):
        if tally[key]:
            print(f"    {label:<12} {tally[key]:>3}  ({tally[key] / judged:.0%})" if judged
                  else f"    {label:<12} {tally[key]:>3}")
    print(f"\njudgments -> {_display(out)}")
    return 0


def run_spotcheck(args) -> int:
    """Print a blind sample for the HUMAN check — labels withheld, key written aside.

    WHY BLIND, and why the key is a separate file: if the reader knows which line is the
    free route's and which is the local model's, the exercise stops measuring quality and
    starts confirming a belief. So the two candidates are printed as 1 and 2 in a random
    order, the arm names go to `local/describer-spotcheck-key.json`, and `--reveal` prints
    them afterwards together with the judge's verdict on the same pair — which is how the
    judge's agreement with a human gets measured rather than assumed.
    """
    pair = [s.strip() for s in args.spotcheck.split(",")]
    if len(pair) != 2:
        print("  --spotcheck wants TWO names, e.g. free16k,local")
        return 2
    left_name, right_name = pair
    key_path = ROOT / "local" / "describer-spotcheck-key.json"

    if args.reveal:
        if not key_path.exists():
            print(f"  no key at {_display(key_path)} - run the spot check first")
            return 2
        key = json.loads(key_path.read_text(encoding="utf-8"))
        verdicts = {}
        jm = Path(args.manifest)
        if jm.exists():
            for line in jm.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if set(d.get("pair", [])) == set(pair):
                    verdicts[d["path"]] = d
        print(f"=== REVEAL: {left_name} vs {right_name} ({len(key['rows'])} modules) ===")
        for r in key["rows"]:
            v = verdicts.get(r["path"], {})
            print(f"\n  {r['path']}")
            print(f"    1 = {r['one']:<9} {r['one_text'][:78]}")
            print(f"    2 = {r['two']:<9} {r['two_text'][:78]}")
            if v:
                print(f"    judge says: {v.get('winner')}  ({v.get('why', '')[:60]})")
        return 0

    arms_manifest = Path(args.arms_manifest)
    rows = ([json.loads(line) for line in arms_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
            if arms_manifest.exists() else [])
    by_path: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_path.setdefault(r["path"], {})[r.get("arm", "chain")] = r
    eligible = [rel for rel, arms in sorted(by_path.items())
                if (arms.get(left_name) or {}).get("generated", "").strip()
                and (arms.get(right_name) or {}).get("generated", "").strip()]

    if not eligible:
        print(f"  nothing to sample yet: no module has BOTH {left_name} and {right_name} answered.")
        print("  (the arms have to have run before there is anything to compare)")
        return 1

    rng = random.Random(args.seed + 3)
    picked = rng.sample(eligible, min(args.spotcheck_n, len(eligible)))
    key = {"pair": pair, "rows": []}
    print(f"=== BLIND SPOT CHECK: {len(picked)} of {len(eligible)} comparable modules "
          f"({left_name} vs {right_name}, labels withheld) ===")
    print("Score each: 1, 2, or tie - then run with --reveal.")
    for rel in picked:
        arms = by_path[rel]
        one_is_left = rng.random() < 0.5
        one = (arms[left_name] if one_is_left else arms[right_name])["generated"]
        two = (arms[right_name] if one_is_left else arms[left_name])["generated"]
        key["rows"].append({
            "path": rel,
            "one": left_name if one_is_left else right_name,
            "two": right_name if one_is_left else left_name,
            "one_text": one,
            "two_text": two,
        })
        size = (TESTS / rel).stat().st_size
        print(f"\n  {rel}  ({size:,} bytes)")
        print(f"    1: {one}")
        print(f"    2: {two}")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"\nkey (do NOT open before scoring) -> {_display(key_path)}")
    return 0



# THE RATER (audit mode): rates the SHIPPED description alone - no generation, no arms.
# Two axes because the first line serves two masters: it documents the module for a
# maintainer AND it is the description a user reads on the testing page. A line can be
# adequate for one and useless for the other, and one score would hide which.
RATER_SYSTEM = (
    "You rate how well a one-line description of a Python test module does its job. You "
    "are given the module's SOURCE and the description the project currently ships.\n"
    "Score TWO axes as integers 0-5.\n"
    "  doc: does the line document the module for a maintainer? "
    "5 = names the concrete behaviours, symbols or edge cases the tests pin down; "
    "3 = true but generic, the file name already implied it; "
    "0 = says nothing, or names a subject these tests do not cover.\n"
    "  reader: does it tell a user what the test does, on a page that lists tests? "
    "5 = someone who has never opened the file knows what is verified; "
    "3 = they learn little beyond the file name; 0 = misleading.\n"
    "Judge only what the tests actually assert: a claim the source does not support is a "
    "defect however specific it sounds. Do not reward length or confidence.\n"
    "THEN ANSWER ONE QUESTION EXPLICITLY, because a score alone cannot carry it: does the "
    "line's central CLAIM match what these tests check? Answer unsupported if the line "
    "names a subject the tests do not cover, or asserts something they never verify - a "
    "WRONG line is not merely a vague one, and it must not be scored as if it were thin.\n"
    'Reply ONLY with JSON: {"doc": <0-5>, "reader": <0-5>, "claim": "supported" or '
    '"unsupported", "why": "<at most 20 words naming what is MISSING or WRONG>"}'
)

RATER = PseudoAgentSpec(
    name="describer-rater",
    system_prompt=RATER_SYSTEM,
    chain=(
        ChainStep(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url=DEEPSEEK_URL,
            has_api_key=True,
            api_key_setting="deepseek_api_key",
        ),
    ),
    temperature=0.0,
    max_tokens=4000,
)


def rate_one(rel: str) -> dict:
    """One call: the source plus the SHIPPED line, scored on the two axes."""
    prompt = (
        f"Describe this test module.\n\n```python\n{source_of(rel)}\n```\n\n"
        f"The description the project currently ships for it: {existing_line(rel)!r}\n"
    )
    t0 = time.monotonic()
    try:
        res = invoke(RATER, prompt)
        raw = res.text
        served_by = res.served_by
    except PseudoAgentError as exc:
        return {"doc": None, "reader": None, "why": str(exc)[:200], "served_by": "-",
                "seconds": round(time.monotonic() - t0, 2)}

    doc = reader = None
    claim, why = None, ""
    blob = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if blob:
        try:
            d = json.loads(blob.group(0))
            doc, reader = d.get("doc"), d.get("reader")
            claim = str(d.get("claim", "")).strip().lower() or None
            why = str(d.get("why", ""))[:160]
        except json.JSONDecodeError:
            why = (raw or "")[:160]
    if not isinstance(doc, int) or not isinstance(reader, int):
        why = why or (raw or "")[:160]
    return {"doc": doc, "reader": reader, "claim": claim, "why": why,
            "served_by": served_by, "seconds": round(time.monotonic() - t0, 2)}


def run_rate(args, out: Path) -> int:
    """AUDIT MODE - rate the shipped descriptions, rank the weak, print the shortlist.

    No arms and no generation: the question is which SHIPPED lines do not do the job, so
    the work a human then has to do is bounded by the score, not by the corpus size.
    """
    modules = select_modules(args.select, args.limit)
    skip = done_paths() if args.resume else set()
    done = short = 0
    for i, rel in enumerate(modules, start=1):
        if (rel, "rate") in skip:
            continue
        # REPEATS, because a single rating jitters by +/-1 on both axes and flipped a
        # module across the weak threshold between two identical runs. The MEAN of several
        # calls is what the threshold reads; the SPREAD is kept, because a module whose
        # scores disagree is exactly the one a human should look at first.
        reps = [rate_one(rel) for _ in range(args.repeats)]
        docs = [x["doc"] for x in reps if isinstance(x["doc"], int)]
        readers = [x["reader"] for x in reps if isinstance(x["reader"], int)]
        r = reps[0]
        r = {**r,
             "repeats": len(reps),
             "doc": round(sum(docs) / len(docs), 2) if docs else None,
             "reader": round(sum(readers) / len(readers), 2) if readers else None,
             "doc_spread": (max(docs) - min(docs)) if docs else None,
             "reader_spread": (max(readers) - min(readers)) if readers else None,
             "doc_all": docs, "reader_all": readers,
             "seconds": round(sum(x["seconds"] for x in reps), 2)}
        row = {"path": rel, "arm": "rate", "current": existing_line(rel), **r}
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        done += 1
        worst = None
        if r["doc"] is not None and r["reader"] is not None:
            worst = min(r["doc"], r["reader"])
        unstable = max(r["doc_spread"] or 0, r["reader_spread"] or 0) >= 2
        low = (r["claim"] == "unsupported"
               or (worst is not None and worst <= args.weak_below)
               or unstable)
        short += bool(low)
        flag = "  <-- WEAK" if low else ""
        print(f"  [{i}/{len(modules)}] {rel}  doc={r['doc']} reader={r['reader']} "
              f"(spread {r['doc_spread']}/{r['reader_spread']}) claim={r['claim']}  "
              f"{r['seconds']}s{flag}", flush=True)
        print(f"      {r['why'][:96]}", flush=True)

    print(f"\n  rated {done}, weak (min score <= {args.weak_below}): {short}")
    print(f"ratings -> {_display(out)}")
    return 0


def main() -> int:
    global MANIFEST  # --manifest overrides it; the row writer and done_paths() both read it
    global GENERATOR  # --arm pins one provider in place of the fallback chain

    ap = argparse.ArgumentParser(description="The describer dry run (generate, judge blind, compare).")
    ap.add_argument("--select", default="all",
                    choices=["all", "sample", "timing", "calibration", "arms30"],
                    help="which modules: all 174, the probe's 5, 5 across the size range, "
                         "the calibration 10, or the stratified arms30 sample")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-judge", action="store_true", help="generate only (the timing gate)")
    ap.add_argument("--offline", action="store_true",
                    help="assemble and print the prompts, make NO calls")
    ap.add_argument("--resume", action="store_true", help="skip modules already in the manifest")
    ap.add_argument("--arm", default="chain", choices=["chain", "free4k", "free16k", "free32k", "local"],
                    help="pin ONE provider (the arms comparison) instead of the fallback chain")
    ap.add_argument("--seed", type=int, default=20260914, help="the A/B shuffle seed")
    ap.add_argument("--rate", action="store_true",
                    help="AUDIT MODE: rate the shipped descriptions, no generation, no arms")
    ap.add_argument("--repeats", type=int, default=3,
                    help="rating calls per module; the mean is scored, the spread is kept")
    ap.add_argument("--weak-below", type=float, default=2.0,
                    help="a module counts as WEAK when min(doc, reader) is at or below this")
    ap.add_argument("--spotcheck", default=None,
                    help="print a BLIND sample of two arms for the human check, e.g. free16k,local")
    ap.add_argument("--spotcheck-n", type=int, default=15, help="how many modules to sample")
    ap.add_argument("--reveal", action="store_true",
                    help="with --spotcheck: print the key and the judge's verdicts")
    ap.add_argument("--judge-compare", default=None,
                    help="judge two arms against each other, e.g. free16k,local "
                         "(reads --arms-manifest, writes --manifest)")
    ap.add_argument("--arms-manifest", default=str(ROOT / "local" / "describer-arms.jsonl"),
                    help="the arms manifest the --judge-compare mode reads")
    ap.add_argument("--manifest", default=str(MANIFEST),
                    help="where the rows are appended (default: local/describer-dryrun.jsonl)")
    args = ap.parse_args()

    MANIFEST = Path(args.manifest)
    GENERATOR = ARMS[args.arm]

    if args.rate:
        return run_rate(args, MANIFEST)
    if args.spotcheck:
        return run_spotcheck(args)
    if args.judge_compare:
        return run_judge_compare(args, MANIFEST)

    modules = select_modules(args.select, args.limit)
    rng = random.Random(args.seed)
    skip = done_paths() if args.resume else set()

    print(f"modules: {len(modules)}  arm: {args.arm}  judge: {not args.no_judge}  "
          f"offline: {args.offline}  manifest: {_display(MANIFEST)}", flush=True)
    if not args.offline:
        environment_report()

    if args.offline:
        rel = modules[0]
        print("\n=== the generator prompt (first module) ===")
        print(f"Describe this test module.\n\n```python\n{source_of(rel)[:800]}\n```")
        print(f"\n=== the judge prompt ({rel}) ===")
        print(f"Describe this test module.\n\n```python\n{source_of(rel)[:800]}\n```\n\n"
              f"Candidate A: <one line>\nCandidate B: <one line>")
        print(f"\n(assembly only - {len(modules)} modules selected, no calls made)")
        return 0

    rows = []
    for i, rel in enumerate(modules, start=1):
        if (rel, args.arm) in skip:
            print(f"  [{i}/{len(modules)}] {rel} - already in the manifest, skipped", flush=True)
            continue
        current = existing_line(rel)
        gen = generate(rel)
        row = {
            "path": rel,
            "arm": args.arm,
            "bytes": (TESTS / rel).stat().st_size,
            "current": current,
            "generated": gen["text"],
            "generated_by": gen["served_by"],
            "generated_seconds": gen["seconds"],
            "generated_degraded": gen["degraded"],
            "generate_error": gen["error"],
            "generate_attempts": gen["attempts"],
        }
        if not args.no_judge:
            if not gen["text"]:
                row["judge"] = {"verdict": "unjudged", "why": "the generator returned nothing"}
            else:
                row["judge"] = judge(rel, current, gen["text"], rng)
        rows.append(row)

        verdict = (row.get("judge") or {}).get("verdict", "-")
        print(f"  [{i}/{len(modules)}] {rel}  {gen['seconds']}s  {verdict}", flush=True)
        print(f"      current  : {current[:88]}", flush=True)
        print(f"      generated: {gen['text'][:88] or '(EMPTY)'}", flush=True)

        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    if rows:
        gen_secs = [r["generated_seconds"] for r in rows]
        print(f"\n  rows appended: {len(rows)}   generate: "
              f"min {min(gen_secs)}s  mean {sum(gen_secs)/len(gen_secs):.1f}s  max {max(gen_secs)}s",
              flush=True)
        judged = [r["judge"]["verdict"] for r in rows if r.get("judge")]
        if judged:
            for v in ("generated", "current", "equal", "unjudged"):
                n = judged.count(v)
                if n:
                    print(f"  judge: {v:<10} {n}  ({n/len(judged):.0%})", flush=True)
    print(f"\nmanifest -> {_display(MANIFEST)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
