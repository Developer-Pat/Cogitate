"""The workflow cost estimator — the prototype (D2).

Takes a corpus + the worker/boss prompt shapes + live OpenRouter
pricing, and prints a per-step estimate. The token math mirrors what
the NODES actually send, including the content truncation — an
estimate that assumes whole files would overstate the input badly.

Run from the repo root:
    .venv/bin/python3 backend/scripts/estimate_workflow_cost.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]
WIKI = ROOT / "wiki"

# ── the shapes the nodes actually build ──────────────────────────────
# the worker prompt: one header line + each page as "--- <path> ---"
# then its content TRUNCATED to 500 chars (tag_survey_nodes.py)
CONTENT_CHARS_PER_FILE = 500
CHARS_PER_TOKEN = 4.0                # the standard English approximation

# CALIBRATED (2026-09-10, the first measured trickle):
#   batch 1: in 631 / out 1609     batch 2: in 633 / out 410
# The prompt overhead was the big miss — the system prompt + the JSON
# contract outweigh the truncated content at this batch size. The
# output variance is the other: 410 vs 1609 on the same shape.
PROMPT_OVERHEAD_TOKENS = 250         # measured, not guessed
OBSERVED_OUTPUT_TOKENS_PER_BATCH = 1000   # the measured MEAN (wide: 410–1609)

# the boss prompt: the counts + the messy variants + the junk
BOSS_INPUT_TOKENS = 900
BOSS_OUTPUT_TOKENS = 400


def fetch_pricing(model_ids: list[str]) -> dict[str, dict]:
    """Live pricing from OpenRouter (per-token → per-million)."""
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", "https://openrouter.ai/api/v1/models"],
        capture_output=True, text=True,
    ).stdout
    data = json.loads(out).get("data", [])
    found = {}
    for m in data:
        if m.get("id") in model_ids:
            p = m.get("pricing", {})
            found[m["id"]] = {
                "in_per_m": float(p.get("prompt", 0)) * 1e6,
                "out_per_m": float(p.get("completion", 0)) * 1e6,
                "name": m.get("name", ""),
            }
    return found


def corpus_stats() -> tuple[int, int]:
    files = sorted(WIKI.rglob("*.md"))
    total_bytes = sum(f.stat().st_size for f in files)
    return len(files), total_bytes


def main() -> None:
    n_files, total_bytes = corpus_stats()
    print("=" * 74)
    print("THE WORKFLOW COST ESTIMATE")
    print("=" * 74)
    print(f"  corpus: {n_files} .md files, {total_bytes:,} bytes "
          f"({total_bytes/1e6:.2f} MB)")

    # ── the batch plan (the atlas probe config) ──────────────────────
    for label, batch_size, max_batches in [
        ("the FULL run (batch_size 3)", 3, None),
        ("the TRICKLE (batch_size 3, max_batches 2)", 3, 2),
        ("a BIGGER probe (batch_size 3, max_batches 20)", 3, 20),
    ]:
        n_batches = (n_files + batch_size - 1) // batch_size
        ran = n_batches if max_batches is None else min(max_batches, n_batches)

        # the input: the prompt overhead + the TRUNCATED content per file
        in_tokens = ran * (
            PROMPT_OVERHEAD_TOKENS
            + batch_size * (CONTENT_CHARS_PER_FILE / CHARS_PER_TOKEN)
        )
        # the output: the observed JSON rows
        out_tokens = ran * OBSERVED_OUTPUT_TOKENS_PER_BATCH
        total_in = in_tokens + BOSS_INPUT_TOKENS
        total_out = out_tokens + BOSS_OUTPUT_TOKENS

        print(f"\n  ── {label}")
        print(f"     batches: {ran} of {n_batches}")
        print(f"     tokens:  in {total_in:>10,.0f}   out {total_out:>8,.0f}")

        # NB: deepseek/deepseek-v4-flash on OpenRouter is the OLD 0423
        # model ($0.087/$0.174). The CURRENT model our chain calls (the
        # direct `deepseek-flash`, i.e. V4.1-Flash) is also on OpenRouter
        # as deepseek/deepseek-v4.1-flash — at EXACTLY the direct price.
        models = [
            "inclusionai/ling-3.0-flash-sante:free",
            "inclusionai/ling-3.0-flash",
            "deepseek/deepseek-v4.1-flash",
            "deepseek/deepseek-v4-flash:free",
            "deepseek/deepseek-v4-flash-0731:batch",
            "qwen/qwen3.5-9b:batch",
        ]
        pricing = fetch_pricing(models)
        for mid in models:
            pr = pricing.get(mid)
            if not pr:
                continue
            cost = (total_in / 1e6) * pr["in_per_m"] + (total_out / 1e6) * pr["out_per_m"]
            print(f"       {mid:<44} ${cost:>8.5f}   "
                  f"(in ${pr['in_per_m']:.3f}/M, out ${pr['out_per_m']:.3f}/M)")

        # THE DIRECT DEEPSEEK (api.deepseek.com) — a DIFFERENT product
        # from OpenRouter's deepseek/* slugs, with different pricing and
        # its own discount mechanism. Our chain's step 3 calls THIS one.
        # https://api-docs.deepseek.com/quick_start/pricing/
        # The direct API's own advantage is not price parity — it is the
        # OFF-PEAK discount (half rate) and cheap CACHE HITS. The worker
        # prompt repeats a stable prefix across all batches, so the cache
        # line is the realistic one for the input side.
        for label, in_per_m, out_per_m in [
            ("DIRECT deepseek  off-peak", 0.15, 0.60),
            ("DIRECT deepseek  PEAK", 0.30, 1.20),
            ("DIRECT deepseek  off-peak + cache hit", 0.003, 0.60),
        ]:
            cost = (total_in / 1e6) * in_per_m + (total_out / 1e6) * out_per_m
            print(f"       {label:<44} ${cost:>8.5f}   "
                  f"(in ${in_per_m:.3f}/M, out ${out_per_m:.3f}/M)")

    print("\n  NOTE: the input math assumes the node's 500-char content")
    print("  truncation. Untruncated files would inflate the input several-fold.")


if __name__ == "__main__":
    main()
