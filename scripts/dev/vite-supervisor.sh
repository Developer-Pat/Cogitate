#!/bin/bash
# THE VITE SUPERVISOR: wraps the dev server — on death it LOGS the
# exit code + the tail of the output, then AUTO-RESTARTS with an
# exponential backoff.
# The evidence lands in logs/vite.log — every start, exit, and
# restart is stamped. A clean exit (0 / the stop-signals) ends
# the loop; a crash restarts.
#
# Usage:   scripts/dev/vite-supervisor.sh
# (the cogitate.sh's start_frontend launches it via setsid)
#
# ── THE MODE ────────────────────────────────────────────────────────────────
# The supervisor serves ONE of two builds, chosen by the launcher through
# COGITATE_FRONTEND_MODE:
#
#   development — the unbundled dev server (hot reload, StrictMode, jsxDEV)
#   production  — the built bundle, served over HTTP
#
# The mode is read ONCE, at launch. A mode change is the launcher stopping this
# supervisor and starting a different one, so there is nothing to re-read — and
# a crashed child always comes back in THIS mode. A supervisor that fell back to
# development would silently undo a switch to production, which would look like
# a flaky switch rather than a design error.
#
# Both modes bind the SAME port (from the vite config, via
# COGITATE_FRONTEND_PORT): the app's state is origin-scoped, so moving the port
# would log the user out and sever the cross-tab channel. cogitate.sh's `mode`
# command owns that invariant.
#
# NOTE ON THE NAME: `vite preview` is Vite's command name for serving a built
# bundle. What it serves IS the production build — the same artifact a
# deployment would ship. Our vocabulary is "production" everywhere else.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
VITE_LOG="$LOG_DIR/vite.log"
mkdir -p "$LOG_DIR"

BACKOFF=2
MAX_BACKOFF=15

trap 'echo "$(date -Is) supervisor stopped (signal)" >> "$VITE_LOG"; exit 0' TERM INT

# THE LOG CAP (2026-09-12): this is a redirect capture with no ceiling, and
# entry #1 taught what that does — 162 MB, invisible to the log page. Rotate it
# HERE, in the loop, because the previous vite has exited and nothing holds the
# fd: the one safe moment.
VITE_LOG_CAP=$((10 * 1024 * 1024))

# THE COMMAND, resolved from the mode. An unrecognised mode fails LOUDLY rather
# than defaulting to development — a silent default here is a mode switch that
# reports success while serving the wrong build.
MODE="${COGITATE_FRONTEND_MODE:-development}"
case "$MODE" in
  development) FRONTEND_CMD=(npx vite) ;;
  production)  FRONTEND_CMD=(npx vite preview) ;;
  *)
    echo "$(date -Is) FATAL unknown mode '$MODE' — expected development or production" >> "$VITE_LOG"
    echo "vite-supervisor: unknown mode '$MODE' (expected development or production)" >&2
    exit 1
    ;;
esac

while true; do
  if [ -f "$VITE_LOG" ]; then
    _size=$(stat -c%s "$VITE_LOG" 2>/dev/null || echo 0)
    if [ "$_size" -ge "$VITE_LOG_CAP" ]; then
      mv -f "$VITE_LOG" "$VITE_LOG.1" 2>/dev/null || true
      gzip -f "$VITE_LOG.1" 2>/dev/null || true
      : > "$VITE_LOG"
      echo "$(date -Is) vite.log rotated ($((_size/1024/1024)) MB)" >> "$VITE_LOG"
    fi
  fi
  echo "$(date -Is) frontend starting (mode=$MODE)" >> "$VITE_LOG"
  (cd "$SCRIPT_DIR/frontend" && exec "${FRONTEND_CMD[@]}" --host 0.0.0.0) >> "$VITE_LOG" 2>&1
  code=$?
  echo "$(date -Is) frontend EXITED (mode=$MODE) code=$code" >> "$VITE_LOG"
  # THE CLEAN-EXIT RULE (2026-09-01, the crash-test lesson): ONLY
  # the code-0 ends the loop — a child's 143/130 (the SIGTERM/SIGINT
  # on the vite itself, e.g. the OOM or a stray kill) RESTARTS. The
  # intentional stop is the supervisor's OWN trap (the cogitate.sh
  # stop kills the process-group — the trap exits cleanly).
  if [ "$code" -eq 0 ]; then
    echo "$(date -Is) supervisor stopping (clean exit)" >> "$VITE_LOG"
    break
  fi
  echo "$(date -Is) restarting in ${BACKOFF}s" >> "$VITE_LOG"
  sleep "$BACKOFF"
  if [ "$BACKOFF" -lt "$MAX_BACKOFF" ]; then BACKOFF=$((BACKOFF * 2)); fi
done
