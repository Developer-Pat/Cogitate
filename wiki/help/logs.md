---
title: Logs & Monitoring
category: logs
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
tags: [domain/help]
---

# Logs & Monitoring

Monitor system activity and debug issues.

## Filters — start here

The filter card is **collapsed by default** behind a bar at the top of
the log list. The bar carries a **Filters** badge (and a count of active
filters — e.g. "2 active" — when any are set). **Click the bar to expand
or collapse the filters.** The badge count tells you a filter is active
even while the card is hidden.

With the card open you can:

- **Search** log messages and sources (top line, next to the time selector)
- **Level** — All Levels / Debug / Info / Warning / Error / Critical
- **Time** — presets (Last 1h / 6h / 12h / 24h / 7d) or a custom range via the Advanced toggle
- **Source** — pick a specific source component (right of the level buttons)
- **Both / Frontend / Backend** — which log files to show (frontend.log, app.log, or both merged)
- **Rows per page** — 25 / 50 / 100 / 250

The **Refresh** button sits in the page header (left of the Help button)
— the list also refreshes itself every second while the page is open.

## Log levels

DEBUG, INFO, WARNING, ERROR, CRITICAL — each level has its own color so
scanning the table by badge is quick. Filter by level to focus on
warnings and errors.

## Clear actions

The row above the filters clears log files. **Clear ALL Logs** is the
red one (frontend + backend + archives history); the amber ones clear
the frontend file, the backend file, or the archived (compressed)
logs individually.

## Test Logs

The **Test Logs** button generates sample entries at every level —
DEBUG through CRITICAL — into the backend log, the frontend log, or
both ("All"). Use it to see what each level looks like and to confirm
the logging pipeline works end to end. The generated entries only show
where the level filter allows, so switch the level filter to
**All Levels** to see the full spread.

## Tips

- Filter by level to focus on warnings and errors
- The Filters bar's count badge shows when something is filtering your view
- Use the Debugging page for detailed error analysis
- System Info shows detailed health checks; Analytics tracks usage trends
