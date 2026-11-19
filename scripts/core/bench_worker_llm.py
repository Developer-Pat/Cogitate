"""Worker-LLM quality benchmark: how well the tag-survey worker LLMs extract, not merely whether they
fire.

A real quality test for the tag-survey worker LLMs — the poke
tells us IF they fire; this tells us HOW WELL they extract.

SCORING (per model, over a fixed corpus):
- recall:     tags found / tags actually in the frontmatter
              (ground truth = the file content, the regex parse)
- noise:      junk tokens echoed (non type/* domain/* tags)
- normalize:  did it fix the known-messy variants?
              (type/devnote -> type/dev-notes)
- contract:   valid JSON array, right shape, no prose?
- latency:    seconds per batch

USAGE: python scripts/core/bench_worker_llm.py
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

# the fixed corpus: clean + known-messy wiki files
CORPUS = [
    "wiki/SCHEMA.md",                        # tags: [domain/root] — clean
    "wiki/Site Index.md",                    # tags: [type/index] — clean
    "wiki/entities/workflow-system.md",      # type/entity domain/entities — clean
    "wiki/help/chat.md",                     # domain/help, no type — a real finding
    "wiki/concepts/cognitive-profiles.md",   # MESSY: "profile pipeline part-code"
    "wiki/dev-notes/known-issues.md",        # MESSY: type/devnote (the variant)
    "wiki/display-tests/diagrams.md",        # MESSY: type/devnote domain/display-tests
]

_FM_RE = re.compile(r"^tags:\s*\[(.*?)\]", re.MULTILINE)


def ground_truth(path: str) -> list:
    """The actual tags in the file (the regex parse = the truth)."""
    p = Path(path)
    if not p.exists():
        return []
    m = _FM_RE.search(p.read_text(encoding="utf-8", errors="ignore"))
    if not m:
        return []
    return [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()]


def score_rows(rows: list, truths: list) -> dict:
    """Score one model's rows against the ground truth."""
    # the model may return rows for some/all files — flatten
    got = set()
    for r in rows:
        for t in (r.get("tags") or []):
            got.add(str(t).strip())
    truth = set(truths)
    recall = len(got & truth) / len(truth) if truth else 1.0
    # noise = non-namespaced junk (no type/ or domain/ prefix)
    noise = [t for t in got if not t.startswith(("type/", "domain/"))]
    # normalization = the model produced type/dev-notes (the fix) vs devnote
    normalized = "type/dev-notes" in got
    return {
        "recall": round(recall, 2),
        "noise": noise,
        "normalized_devnote": normalized,
    }


def run_model(llm_factory, model: str, label: str) -> dict:
    """Run one model over the corpus via the worker prompt."""
    results = []
    t0 = time.time()
    for path in CORPUS:
        p = Path(path)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8", errors="ignore")[:500]
        prompt = (
            "Extract the YAML frontmatter tags from each page below. "
            "Return ONLY a JSON array of objects: [{\"page\": <path>, \"tags\": [<tags>]}]. "
            "Do not add prose. If a page has no tags, return an empty tags array.\n\n"
            + f"--- {path} ---\n{content}"
        )
        try:
            llm = llm_factory(model)
            resp = llm.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            _s, _e = text.find("["), text.rfind("]")
            if _s >= 0 and _e > _s:
                rows = json.loads(text[_s:_e + 1])
            else:
                rows = []
            if not isinstance(rows, list):
                rows = []
            results.append(rows)
        except Exception as e:
            results.append([{"error": str(e)[:80]}])
    dt = time.time() - t0

    # aggregate
    truths = []
    for path in CORPUS:
        truths.extend(ground_truth(path))
    all_rows = [r for batch in results for r in batch if isinstance(r, dict) and "error" not in r]
    sc = score_rows(all_rows, truths)
    sc["latency_s"] = round(dt, 1)
    sc["files"] = len(CORPUS)
    return sc


def main():
    from app.domain.providers.config_service import ProviderConfig
    from app.domain.providers.llm_factory import get_llm_from_config
    from app.core.config import get_settings

    settings = get_settings()
    models = []

    def granite_factory(model):
        return get_llm_from_config(
            ProviderConfig(provider_type="ollama", base_url="http://localhost:11434",
                           name="ollama", config={"default_model": model}, has_api_key=False),
            temperature=0.0, max_tokens=2000)

    def or_factory(model):
        return get_llm_from_config(
            ProviderConfig(provider_type="openrouter", base_url="https://openrouter.ai/api/v1",
                           name="openrouter", config={"default_model": model}, has_api_key=True),
            temperature=0.0, max_tokens=2000, api_key=settings.openrouter_api_key)

    candidates = [
        ("granite4:3b (local)", granite_factory, "granite4:3b"),
        ("z-ai/glm-5.2 (free)", or_factory, "z-ai/glm-5.2:free"),
        ("google/gemma-4-31b (free)", or_factory, "google/gemma-4-31b-it:free"),
        ("google/gemma-4-26b (free)", or_factory, "google/gemma-4-26b-a4b-it:free"),
        ("openai/gpt-oss-20b (free)", or_factory, "openai/gpt-oss-20b:free"),
        ("thinkingmachines/inkling (free)", or_factory, "thinkingmachines/inkling:free"),
        ("dots-studio/dots-3 (free)", or_factory, "dots-studio/dots-3-note-preview:free"),
        ("poolside/laguna-s-2.1 (free)", or_factory, "poolside/laguna-s-2.1:free"),
        ("nvidia/nemotron-3.5-lightning (free)", or_factory, "nvidia/nemotron-3.5-lightning:free"),
        ("nvidia/nemotron-3-nano-30b (free)", or_factory, "nvidia/nemotron-3-nano-30b-a3b:free"),
        ("nvidia/nemotron-3-ultra (free)", or_factory, "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ]

    print(f"\n=== The worker-LLM quality benchmark ({len(CORPUS)} files) ===")
    print(f"{'model':28s} {'recall':7s} {'noise':30s} {'norm':6s} {'sec':6s}")
    print("-" * 80)
    for label, factory, model in candidates:
        try:
            sc = run_model(factory, model, label)
            print(f"{label:28s} {sc['recall']:<7.2f} {str(sc['noise'])[:28]:30s} {str(sc['normalized_devnote']):6s} {sc['latency_s']:<6.1f}")
        except Exception as e:
            print(f"{label:28s} FAILED: {str(e)[:60]}")


if __name__ == "__main__":
    main()
