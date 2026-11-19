"""Consult tool — ask the external agent (Hermes/OpenClaw) for a
second opinion.

The Consulting Agent capability: a Cogitate agent passes its
OBSERVED STATE + a QUESTION ("here's what I see, what do you
actually see?") and the external agent's answer returns into the
agent's context.

BOUNDARY CONTRACT (decided 2026-08-11/12, binding):
- ONLY the explicitly-passed `context` + `question` travel to the
  external agent. Never raw session state, conversation store, DB.
- Hard timeout: the agent pipeline must never hang on a slow
  consultant — returns a graceful error string instead.
- See wiki/dev-notes/agents/consulting-agent.md for the full
  design (skills, rooting, RAG via context builder).

Naming: 'Consulting Agent' = feature, 'External Agent' =
technology, `consult` = this tool slug.
"""

from __future__ import annotations

import asyncio
from typing import Any
from app.core.config import Paths
from app.domain.external_agent.services import ExternalAgentInactive

# how long a consult may take before the agent pipeline moves on
CONSULT_TIMEOUT_SECONDS = 90


async def consult_handler(config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Consult the external agent with observed state + a question.

    Args (kwargs):
        context: what the agent observes (state, logs, snippet,
            error) — the ONLY information sent outward
        question: the question to ask the consultant
        skill_hint: optional — name of a Cogitate skill the
            consultant should follow (e.g. 'create-agent'); the
            tool reads the SKILL.md and includes it in the prompt
            (consult-tool-injected delivery, decision 2026-08-12)
    """
    context = str(kwargs.get("context", "")).strip()
    question = str(kwargs.get("question", "")).strip()
    skill_hint = str(kwargs.get("skill_hint", "")).strip()

    if not question:
        return {"success": False, "error": "question is required"}
    if not context:
        return {"success": False, "error": "context is required (the consultant sees only what you pass)"}

    # build the prompt
    parts: list[str] = []
    if skill_hint:
        skill_body = _load_skill(skill_hint)
        if skill_body:
            parts.append(f"[Cogitate skill: {skill_hint}]\n{skill_body}")
        else:
            parts.append(f"[Cogitate skill: {skill_hint} — not found, answer generally]")
    parts.append("[Context from the requesting agent — treat as ground truth of what it observes]")
    parts.append(context)
    parts.append(f"[Question]\n{question}")
    prompt = "\n\n".join(parts)

    try:
        from app.domain.external_agent import get_acp_client

        client = get_acp_client()
        if not client.connected:
            try:
                await asyncio.wait_for(client.start(), timeout=30)
            except asyncio.TimeoutError:
                return {"success": False, "error": "consult failed: could not start the external agent (30s)"}
            except ExternalAgentInactive as e:
                # switched off is a STATE, not a failure: report it plainly so
                # the calling agent can tell the user rather than retrying
                return {"success": False, "inactive": True, "error": str(e)}
        try:
            reply = await asyncio.wait_for(client.prompt(prompt), timeout=CONSULT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"consult timed out after {CONSULT_TIMEOUT_SECONDS}s (the external agent was too slow)",
            }
        return {"success": True, "reply": reply}
    except Exception as e:  # never let a consult break the agent pipeline
        return {"success": False, "error": f"consult failed: {e}"}


def _load_skill(name: str) -> str:
    """Read a SKILL.md from skills/cogitate/ by name (consult-tool-
    injected delivery).

    Matches either the DIRECTORY name (e.g. 'orientation') or the
    frontmatter 'name' (e.g. 'cogitate-orientation') — the two can
    differ (directories are short; frontmatter names are namespaced).
    """

    root = Paths.skills_dir / "cogitate"
    # 1. direct directory match
    target = root / name / "SKILL.md"
    if target.exists():
        try:
            return target.read_text(encoding="utf-8")
        except OSError:
            return ""
    # 2. scan skill dirs for a frontmatter-name match
    for child in root.iterdir() if root.is_dir() else []:
        candidate = child / "SKILL.md"
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = text.split("---", 2)
        if len(fm) >= 2 and f"name: {name}" in fm[1]:
            return text
    return ""

    root = Paths.skills_dir / "cogitate"
    target = root / name / "SKILL.md"
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return ""
