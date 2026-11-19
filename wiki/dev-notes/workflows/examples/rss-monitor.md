---
title: Example — RSS News Monitor
type: atlas-example
category: workflows
order: 1
confidence: high
created: 2026-08-10
updated: 2026-08-10
tags: [type/example, domain/workflows]
---

# Example: RSS News Monitor (`rss-monitor`)

> What it is: a personal news digest. Every hour it fetches your
> configured RSS feeds, keeps a "last seen" record so you only
> ever see **new** stories, and writes a markdown digest file.
> No feed reader, no repeats.

## Why you'd use it

Instead of checking five sites, you open one file. The default
seed uses Hacker News + Ars Technica; you can set any feeds via
`inputs.feeds`.

## Real output

Run 1 (live 2026-08-10 — 5 fresh Hacker News stories):

```markdown
# RSS Digest — 2026-08-10T01:02:44Z

_Items: 5 · Errors: 0_

## New items

- **To Recruit Teachers, School Districts Are Building Homes** (https://hnrss.org/frontpage)
  https://www.nytimes.com/2026/07/28/business/...
- **AI assistant hacks gym website in first known Australian aut...** (https://hnrss.org/frontpage)
  https://www.abc.net.au/news/2026-08-10/...
- **Georgia police officers fired after Flock camera misuse** (https://hnrss.org/frontpage)
  https://www.wtoc.com/2026/08/07/...
```

Run 2 (the dedup in action):

```markdown
# RSS Digest — 2026-08-10T01:04:00Z

_Items: 0 · Errors: 0_

No new items this cycle.
```

## How to read it

- `_Items: N_` — how many new stories since the last run
- Each item links back to the source
- With `summarize-llm` configured, the digest becomes
  LLM-summarized bullet points instead of raw headlines
- `Errors: N` — a dead feed records an error but never fails the run

## Run it

`POST /api/v1/workflows/execute` with `template_id: rss-monitor`
and `inputs: {"feeds": [...], "max_items": 5}` — or just let the
hourly trigger (`monitor-rss-hourly`) do it.

## Related

- [[dev-notes/workflows/monitor-family|Monitor Workflow Family]]
