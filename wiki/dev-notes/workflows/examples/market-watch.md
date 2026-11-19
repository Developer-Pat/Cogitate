---
title: Example — Market Watch
type: atlas-example
category: workflows
order: 2
confidence: high
created: 2026-08-10
updated: 2026-08-10
tags: [type/example, domain/workflows]
---

# Example: Market Watch (`market-watch`)

> What it is: a price tripwire. Every 5 minutes it fetches a
> crypto price (CoinGecko, no API key), compares it to the last
> price it saw, and writes an alert file when the move exceeds
> your threshold. No chart-watching.

## Why you'd use it

Set `symbol: bitcoin`, `threshold_pct: 2.0`, and the system tells
you when BTC moves more than 2% — the only thing you check is the
alert file.

## Real output

Quiet run (within threshold):

```markdown
# Market Watch — 2026-08-10T01:04:13Z

- bitcoin: $64,959.00 (change -0.08% — within threshold)
```

Alert run (threshold tripped):

```markdown
- bitcoin: $66,300.00 (▲ up +2.00% vs $65,000.00)
```

## How to read it

- `▲ up / ▼ down` + percentage — direction and magnitude vs the
  previous 5-minute check
- A quiet run just records the price; a trip writes the alert
- The "last price" persists in `data/monitor/state.json`

## Run it

`POST /api/v1/workflows/execute` with `template_id: market-watch`
and `inputs: {"symbol": "bitcoin", "threshold_pct": 2.0}` — or
the 5-minute trigger (`monitor-market-5min`) does it for you.

## Related

- [[dev-notes/workflows/monitor-family|Monitor Workflow Family]]
