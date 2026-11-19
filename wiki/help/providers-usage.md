---
title: Usage Statistics
category: providers-usage
subtopic: Provider Usage
order: 1
confidence: high
created: 2026-08-03
tags: [domain/help]
---

# Usage Statistics

The Usage tab summarizes token consumption, cost, request counts, and
response times from `usage_logs`.

## What you see

- **Period selector** — Daily / Weekly / Monthly / All Time.
- **Totals** — tokens (prompt + completion), cost, request count
  (successful vs failed), average response time.
- **Usage Trend** — tokens over time.
- **Cost by Provider** — per-provider cost split.
- **Usage by Model** — per-model token/request/cost table.

## Notes

- Costs are $0.0000 for local (Ollama) and free-tier models — that is
  expected, not a bug.
- Failed requests count separately (e.g. provider errors, dead models).
  Persistent failures on a model suggest it is stale — check the
  **Health** tab and the agent health badges.
- Response time averages include failures, so a spike usually indicates
  an outage or a dead model, not slow models.

## Tips

- Use the period selector to see recent vs historical trends.
- A model showing repeated failures should be removed from the curated
  list or the agent reconfigured (see the Curated tab).
