---
name: restart-cogitate
description: "Use when needing to cleanly restart the Cogitate development environment or clear zombie processes."
version: 1.0.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [devops, restart, server]
    related_skills: []
---

# Restart Cogitate

## Overview

Cleanly stop and restart the Cogitate backend and frontend services. Handles zombie Vite/esbuild processes that accumulate over multiple restarts.

## When to Use

- Cogitate is unresponsive or showing stale data
- After making backend or frontend code changes that require a full restart
- The frontend shows "connection lost" or backend returns 500 errors
- Multiple orphaned Vite processes are consuming memory
- The agent is running stale code

Do NOT use for:
- Simple hot-reload scenarios (the dev server auto-reloads for most code changes)
- Database-only issues (restarting won't fix corrupted data)

## Steps

1. Stop the current services:

   ```bash
   cd ~/Projects/cogitate && ./cogitate.sh stop
   ```

2. Kill any leftover zombie processes:

   ```bash
   pkill -f "node.*vite" 2>/dev/null; pkill -f "esbuild" 2>/dev/null; echo "Zombies cleaned"
   ```

3. Wait a moment for ports to release:

   ```bash
   sleep 2
   ```

4. Start fresh:

   ```bash
   ./cogitate.sh start
   ```

5. Wait for readiness (check every 5 seconds):

   ```bash
   sleep 3 && curl -s http://localhost:8000/api/v1/health
   ```

## Common Pitfalls

1. **Stop fails because PID file is stale.** Run `pkill -f uvicorn` and `pkill -f vite` manually.
2. **Frontend port 5173 is occupied.** Check with `lsof -i :5173` and kill the process.
3. **Backend starts but frontend hangs.** Wait 30 seconds — Vite needs time to compile on first load.
4. **Multiple restart attempts create more zombies.** Always run `stop` + zombie cleanup before `start` — never `start` twice.

## Verification Checklist

- [ ] `curl -s http://localhost:8000/api/v1/health` returns a JSON with "status":"ok"
- [ ] Frontend loads at http://localhost:5173 without errors
- [ ] An agent chat round-trip responds (the ACP/external-agent endpoint)
