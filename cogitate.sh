#!/bin/bash
# =============================================================================
# Cogitate - Development Environment Manager
# =============================================================================
# Manages backend and frontend services with proper signal handling,
# crash detection, and logging.
#
# Usage:
#   ./cogitate.sh install   - Install the toolchain and dependencies (first run)
#   ./cogitate.sh start     - Start all services
#   ./cogitate.sh stop      - Stop all services
#   ./cogitate.sh restart   - Restart all services
#   ./cogitate.sh status    - Show service status
#   ./cogitate.sh logs      - Show recent logs
#   ./cogitate.sh help      - Show this help
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/logs"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

# Log files — consolidated under backend/logs/ so all backend output
# (Python logging + uvicorn stdout/stderr) lives in the same directory.
BACKEND_LOG="$BACKEND_DIR/logs/console.log"
FRONTEND_LOG="$LOG_DIR/frontend_startup.log"

# ── PORTS (2026-09-15) ───────────────────────────────────────────────────────
# The defaults, and the ONE place to change them. Both are env-overridable so a
# second instance can run beside the first:
#
#     COGITATE_BACKEND_PORT=8100 COGITATE_FRONTEND_PORT=5273 ./cogitate.sh start
#
# Everything downstream derives from these — the bind, the health checks, the
# stop path, and (exported) the frontend's dev server and its API proxy. Nothing
# else in this script may hardcode a port.
BACKEND_PORT="${COGITATE_BACKEND_PORT:-8000}"
FRONTEND_PORT="${COGITATE_FRONTEND_PORT:-5173}"

# Exported so the frontend's vite config and the backend's CORS default agree
# with what the launcher actually bound. Without this the proxy would still aim
# at 8000 while the backend listened on 8100 — a silent, confusing failure.
export COGITATE_BACKEND_PORT="$BACKEND_PORT"
export COGITATE_FRONTEND_PORT="$FRONTEND_PORT"

BACKEND_URL="http://localhost:${BACKEND_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

# ── THE FRONTEND MODE (2026-09-17) ──────────────────────────────────────────
# Which build the frontend serves. Two modes — and THE PORT IS NOT PART OF THE
# DIFFERENCE, on purpose:
#
#   development — the unbundled dev server (hot reload, StrictMode, jsxDEV)
#   production  — the built bundle, served over HTTP
#
# WHY ONE PORT. The app's state lives in ORIGIN-SCOPED browser storage: the auth
# token, five persisted zustand stores (settings, message history, prompt
# history) and the cross-tab BroadcastChannel all key off scheme+host+PORT. A
# production server on a second port would log the user out, empty their
# history, and sever the very channel that coordinates the tabs through the
# switch — so the mode changes what is served, never where.
#
# The mode PERSISTS in $FRONTEND_MODE_FILE so a `restart`, or a stop/start
# round-trip, comes back in the mode the user chose instead of silently
# reverting to development.
FRONTEND_MODE_FILE="$PID_DIR/frontend.mode"
FRONTEND_MODE="development"
if [ -f "$FRONTEND_MODE_FILE" ]; then
    _saved_mode=$(tr -d '[:space:]' < "$FRONTEND_MODE_FILE" 2>/dev/null)
    case "$_saved_mode" in
        development|production) FRONTEND_MODE="$_saved_mode" ;;
    esac
fi

# Exported so the supervisor inherits it — it reads the mode ONCE, at launch.
export COGITATE_FRONTEND_MODE="$FRONTEND_MODE"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

# ---------------------------------------------------------------------------
# THE LOG CAP (2026-09-12, the 162 MB console.log).
#
# `console.log` and `logs/vite.log` are not managed logs — they are raw
# redirect captures, so nothing rotates them and nothing caps them. During the
# 2026-09-11 flood console.log reached 162 MB, and the log PAGE could not even
# see it (it reads the managed frontend.log/app.log only), so the UI reported
# calm while the file that broke things grew behind it.
#
# Rotation happens at START, deliberately: both files are held open by a shell
# redirect while the app runs, so truncating a live one leaves a sparse hole
# and the writer carries on from its old offset. At start nothing holds them.
#
# One prior generation is kept, gzipped — enough to inspect a crash — and the
# rotation is announced, because a silent cap is how you lose the evidence you
# needed. Tune the ceiling here; 10 MB is generous for a dev log.
# ---------------------------------------------------------------------------
LOG_CAP_MB=10
LOG_CAP_BYTES=$((LOG_CAP_MB * 1024 * 1024))

rotate_log() {
    local f="$1"
    [ -f "$f" ] || return 0
    local size
    size=$(stat -c%s "$f" 2>/dev/null || echo 0)
    if [ "$size" -lt "$LOG_CAP_BYTES" ]; then
        return 0
    fi
    local mb=$((size / 1024 / 1024))
    # Move the live file aside, keep ONE prior generation gzipped, start fresh.
    mv -f "$f" "$f.1" 2>/dev/null || true
    if gzip -f "$f.1" 2>/dev/null; then
        : > "$f"
        log_warning "Rotated $(basename "$f") (${mb} MB) -> $(basename "$f").1.gz"
    else
        : > "$f"
        log_warning "Rotated $(basename "$f") (${mb} MB) -> $(basename "$f").1"
    fi
}

rotate_logs() {
    rotate_log "$BACKEND_LOG"
    rotate_log "$LOG_DIR/vite.log"
}

# Rotate ONLY on a clean start. `cmd_start` is also reachable while the app is
# up (it then reports "already running" and leaves it alone) — and rotating a
# live capture is exactly what this is meant to avoid. Say so rather than
# skipping silently. A long-running session can still grow a capture; the floor
# on the frontend logger (2026-09-11) removed the growth that caused 162 MB,
# and the supervisor caps its own log between restarts.
rotate_logs_if_stopped() {
    local bp=$(get_pid "$BACKEND_PID_FILE")
    local fp=$(get_pid "$FRONTEND_PID_FILE")
    if is_process_running "$bp" || is_process_running "$fp"; then
        log_info "Log rotation skipped — the app is running (it rotates on a clean start)"
        return 0
    fi
    rotate_logs
}

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if a process is running
is_process_running() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

# Get PID from file
get_pid() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    fi
}

# Save PID to file
save_pid() {
    local pid_file=$1
    local pid=$2
    echo "$pid" > "$pid_file"
}

# Clean PID file
clean_pid() {
    local pid_file=$1
    rm -f "$pid_file"
}

# Wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local attempt=1

    log_info "Waiting for $name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            log_success "$name is ready (attempt $attempt)"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    
    log_error "$name failed to start after $max_attempts seconds"
    return 1
}

# =============================================================================
# Service Management Functions
# =============================================================================

start_backend() {
    log_info "Starting backend server..."
    
    # Check if already running
    local existing_pid=$(get_pid "$BACKEND_PID_FILE")
    if is_process_running "$existing_pid"; then
        log_warning "Backend already running (PID: $existing_pid)"
        return 0
    fi
    
    # Clean old PID file
    clean_pid "$BACKEND_PID_FILE"
    
    # Start backend with setsid (prevents signal death)
    # Note: Using --log-level to let our app handle logging configuration
    # --reload enables hot-reload for code changes (prevents stale code issues)
    # THE 2026-09-01 REFRESH: the project venv (uv-era -> the .venv's
    # python3) + the env-unsets (CORS_ORIGINS breaks pydantic; the
    # sweep/inbox delays the runtime needs).
    cd "$BACKEND_DIR"
    setsid env -u CORS_ORIGINS \
        INBOX_PROCESSOR_INTERVAL_SECONDS=20 SYSTEM_SWEEP_DELAY_SECONDS=15 \
        ../.venv/bin/python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --log-level info \
        --timeout-graceful-shutdown 15 \
        --reload \
        > "$BACKEND_LOG" 2>&1 &
    
    local new_pid=$!
    save_pid "$BACKEND_PID_FILE" "$new_pid"
    
    # Wait for startup
    if wait_for_service "$BACKEND_URL/api/v1/health" "Backend"; then
        log_success "Backend started (PID: $new_pid)"
        return 0
    else
        log_error "Backend failed to start. Check logs:"
        tail -20 "$BACKEND_LOG"
        clean_pid "$BACKEND_PID_FILE"
        return 1
    fi
}

start_frontend() {
    log_info "Starting frontend server..."
    
    # Check if already running
    local existing_pid=$(get_pid "$FRONTEND_PID_FILE")
    if is_process_running "$existing_pid"; then
        log_warning "Frontend already running (PID: $existing_pid)"
        return 0
    fi
    
    # Clean old PID file
    clean_pid "$FRONTEND_PID_FILE"
    
    # Start frontend with setsid (CRITICAL: prevents SIGTERM death)
    # THE 2026-09-01 REFRESH: the VITE SUPERVISOR (the recurring-
    # death dig) — the wrapper logs the exit evidence + auto-
    # restarts; the evidence lands in logs/vite.log.
    setsid bash "$SCRIPT_DIR/scripts/dev/vite-supervisor.sh" > "$FRONTEND_LOG" 2>&1 &
    
    local new_pid=$!
    save_pid "$FRONTEND_PID_FILE" "$new_pid"
    
    # Wait for startup
    if wait_for_service "$FRONTEND_URL" "Frontend" 15; then
        log_success "Frontend started (PID: $new_pid)"
        return 0
    else
        log_error "Frontend failed to start. Check logs:"
        tail -20 "$FRONTEND_LOG"
        clean_pid "$FRONTEND_PID_FILE"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# THE GROUP STOP (2026-09-12, the orphan bug).
#
# The app is started with `setsid` on purpose — so it survives a terminal
# closing, and so a stray SIGTERM to the launcher does not take the dev server
# with it. The cost, discovered the hard way: BOTH trees are signal-isolated,
# and the old stop killed only the PID recorded in the file. For the frontend
# that is the supervisor; its children (npm -> sh -> node/vite -> esbuild) were
# never touched, so `stop` printed "✅ Frontend stopped" while three processes
# kept holding 5173. Killing the recorded PID again found nothing to kill —
# which is why `pkill -f` appeared to do nothing and only `kill -9 <pid>` on
# the individual children worked.
#
# The fix is to kill the whole process GROUP (negative PID), which reaches
# every descendant the setsid tree contains. Then VERIFY, and report what
# actually happened rather than announcing success unconditionally.
# ---------------------------------------------------------------------------
stop_process_group() {
    local name="$1"
    local pid_file="$2"
    local port="$3"
    local pid=$(get_pid "$pid_file")

    if ! is_process_running "$pid"; then
        log_info "$name not running"
        clean_pid "$pid_file"
        return 0
    fi

    # The PGID leads the setsid'd tree. It is normally equal to $pid, but read
    # it rather than assume — setsid forks when it is already a group leader.
    local pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
    log_info "Stopping $name (PID: $pid, PGID: ${pgid:-?})..."

    # TERM the GROUP, not the process: the descendants are detached, so
    # signalling only $pid orphans them.
    if [ -n "$pgid" ]; then
        kill -TERM "-$pgid" 2>/dev/null || true
    else
        kill -TERM "$pid" 2>/dev/null || true
    fi

    local attempts=0
    while is_process_running "$pid" && [ $attempts -lt 10 ]; do
        sleep 1
        attempts=$((attempts + 1))
    done

    if is_process_running "$pid"; then
        log_warning "$name didn't stop gracefully, forcing..."
        if [ -n "$pgid" ]; then
            kill -9 "-$pgid" 2>/dev/null || true
        else
            kill -9 "$pid" 2>/dev/null || true
        fi
        sleep 1
    fi

    # THE VERIFY (the part that was missing): anything still in the group
    # after a group kill is a real survivor, and saying so beats a lie.
    local survivors=""
    if [ -n "$pgid" ]; then
        survivors=$(pgrep -g "$pgid" 2>/dev/null | tr '\n' ' ' || true)
    fi

    clean_pid "$pid_file"

    if [ -n "$survivors" ]; then
        log_warning "$name: survivors remain after the group kill: $survivors"
        for s in $survivors; do kill -9 "$s" 2>/dev/null || true; done
        sleep 1
    fi

    # Final word: the port, which is what actually matters.
    if [ -n "$port" ] && command -v ss >/dev/null 2>&1; then
        if ss -lptn "sport = :$port" 2>/dev/null | grep -q LISTEN; then
            log_warning "$name stopped, but port $port is STILL HELD"
            return 1
        fi
    fi

    log_success "$name stopped"
}

stop_backend() {
    stop_process_group "Backend" "$BACKEND_PID_FILE" "$BACKEND_PORT"
}

stop_frontend() {
    stop_process_group "Frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
}

# =============================================================================
# Command Implementations
# =============================================================================

cmd_start() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║     🚀 Starting Cogitate Development Environment        ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    
    # Ensure directories exist
    mkdir -p "$PID_DIR" "$LOG_DIR"

    # THE LOG CAP — rotate the unmanaged captures, but only when nothing holds
    # them open (see rotate_logs_if_stopped).
    rotate_logs_if_stopped
    
    local backend_ok=true
    local frontend_ok=true
    
    # Start backend
    start_backend || backend_ok=false
    
    # Start frontend
    start_frontend || frontend_ok=false
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                  📊 Startup Summary                      ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    
    if $backend_ok; then
        log_success "Backend:  $BACKEND_URL"
    else
        log_error "Backend:  FAILED"
    fi
    
    if $frontend_ok; then
        log_success "Frontend: $FRONTEND_URL"
    else
        log_error "Frontend: FAILED"
    fi
    
    echo ""
    
    if $backend_ok && $frontend_ok; then
        echo "  Access the application: $FRONTEND_URL"
        echo ""
        echo "  To stop: ./cogitate.sh stop"
        echo "  To restart: ./cogitate.sh restart"
        echo "  To view logs: ./cogitate.sh logs"
        echo ""
        return 0
    else
        log_error "One or more services failed to start"
        echo ""
        echo "Check logs with: ./cogitate.sh logs"
        return 1
    fi
}

cmd_stop() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║     🛑 Stopping Cogitate Development Environment         ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    
    stop_frontend
    stop_backend
    
    echo ""
    log_success "All services stopped"
    echo ""
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

# ---------------------------------------------------------------------------
# THE MODE SWITCH (2026-09-17).
#
# Switches the frontend between the two builds WITHOUT moving the port — see the
# frontend-mode block at the top for why the origin must not change.
#
# The order is load-bearing, not cosmetic:
#
#   1. THE BUILD, FIRST (production only). It is the one step that can plausibly
#      fail, so it runs while the current server is still serving: a failure
#      then costs nothing. Doing it after the stop would leave the user with no
#      frontend at all.
#   2. THE STOP. The supervisor's whole process GROUP goes down — killing only
#      the recorded pid orphans the npm -> sh -> node/vite chain, which keeps
#      holding the port. stop_process_group verifies the port is actually
#      released and says so if it is not.
#   3. THE START, on the same port, then wait_for_service proves it came up.
#
# A mode change is NOT a build-free operation (production needs the bundle) but
# it is also not a restart of the backend: only the frontend cycles, so an
# in-flight backend task survives.
# ---------------------------------------------------------------------------
cmd_mode() {
    local target="$1"

    case "$target" in
        dev|development)   target="development" ;;
        prod|production)   target="production" ;;
        ""|status)
            log_info "Frontend mode: $FRONTEND_MODE"
            echo "  usage: ./cogitate.sh mode development|production"
            return 0
            ;;
        *)
            log_error "Unknown mode: $target"
            echo "  usage: ./cogitate.sh mode development|production"
            return 1
            ;;
    esac

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║     🔀  Switching the frontend mode                      ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

    if [ "$target" = "$FRONTEND_MODE" ] && is_process_running "$(get_pid "$FRONTEND_PID_FILE")"; then
        log_info "Frontend is already serving $target — nothing to do"
        return 0
    fi

    # ── 1. THE BUILD GATE (production only, and it comes first) ────────────
    if [ "$target" = "production" ]; then
        log_info "Building the production bundle (~70s — this is the slow part)..."
        mkdir -p "$LOG_DIR"
        if (cd "$FRONTEND_DIR" && npm run build) > "$LOG_DIR/mode-build.log" 2>&1; then
            log_success "Build complete"
        else
            log_error "Build FAILED — the frontend is untouched, still in $FRONTEND_MODE mode"
            echo "  last lines of $LOG_DIR/mode-build.log:"
            tail -5 "$LOG_DIR/mode-build.log" | sed 's/^/    /'
            return 1
        fi
    fi

    # ── 2. THE STOP (the same port must be released before the rebind) ─────
    export COGITATE_FRONTEND_MODE="$target"
    if ! stop_frontend; then
        log_error "The frontend did not stop cleanly — not switching (the port is still held)"
        export COGITATE_FRONTEND_MODE="$FRONTEND_MODE"
        return 1
    fi

    mkdir -p "$PID_DIR"
    printf '%s\n' "$target" > "$FRONTEND_MODE_FILE"
    FRONTEND_MODE="$target"

    # ── 3. THE START, on the same port, verified ──────────────────────────
    if start_frontend; then
        echo ""
        log_success "Frontend is now serving $target mode"
        echo "  Reload your browser tabs — they are still running the previous build."
        echo ""
        return 0
    fi

    log_error "Frontend failed to start in $target mode"
    log_info "The mode file records '$target'. To go back: ./cogitate.sh mode development"
    return 1
}

cmd_status() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║            📋 Cogitate Service Status                    ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    
    # Backend status
    local backend_pid=$(get_pid "$BACKEND_PID_FILE")
    if is_process_running "$backend_pid"; then
        log_success "Backend:  Running (PID: $backend_pid)"
        curl -s "$BACKEND_URL/api/v1/health" 2>/dev/null && echo "" || log_warning "Health check failed"
    else
        log_error "Backend:  Stopped"
        [ -n "$backend_pid" ] && log_warning "Stale PID file (process not running)"
    fi
    
    echo ""
    
    # Frontend status — and WHICH BUILD it serves. The two builds are otherwise
    # behaviourally identical, so the mode is the only thing that explains why
    # the UI feels different, and status is where the user looks to find out.
    local frontend_pid=$(get_pid "$FRONTEND_PID_FILE")
    if is_process_running "$frontend_pid"; then
        log_success "Frontend: Running (PID: $frontend_pid, mode: $FRONTEND_MODE)"
        curl -s "$FRONTEND_URL" > /dev/null 2>&1 && log_success "Responding on $FRONTEND_URL" || log_warning "Not responding"
    else
        log_error "Frontend: Stopped"
        log_info "Mode recorded: $FRONTEND_MODE"
        [ -n "$frontend_pid" ] && log_warning "Stale PID file (process not running)"
    fi
    
    echo ""
    
    # Show all related processes
    echo "Related processes:"
    ps aux | grep -E "uvicorn|vite|npm.*dev" | grep -v grep | awk '{printf "  PID %s: %s\n", $2, $11}'
    
    echo ""
}

cmd_logs() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              📜 Recent Service Logs                      ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "=== Backend Startup Log ==="
    if [ -f "$BACKEND_LOG" ]; then
        tail -30 "$BACKEND_LOG"
    else
        echo "No backend log found"
    fi
    
    echo ""
    echo "=== Frontend Startup Log ==="
    if [ -f "$FRONTEND_LOG" ]; then
        tail -30 "$FRONTEND_LOG"
    else
        echo "No frontend log found"
    fi
    
    echo ""
    echo "=== Application Logs ==="
    if [ -d "$LOG_DIR" ]; then
        ls -la "$LOG_DIR"/*.log 2>/dev/null | awk '{print "  " $9}'
        echo ""
        echo "View full logs:"
        echo "  Backend:  tail -f $BACKEND_LOG"
        echo "  Frontend: tail -f $FRONTEND_LOG"
        echo "  App:      tail -f $LOG_DIR/app.log"
    fi
    
    echo ""
}

# =============================================================================
# INSTALL — the one bootstrap (2026-11-18, Phase D)
# =============================================================================
# THE CONTRACT: a fresh clone plus this one command is a working install. Every
# other delivery path (a .deb, an agent-driven install) is a wrapper over THIS
# function, so what it does is what "installed" is allowed to mean.
#
# WHAT IT TOUCHES, and why each piece is here:
#   git    — apt. Needed to clone, and what a contributor keeps anyway.
#   uv     — astral's installer into ~/.local/bin. It brings its OWN Python 3.14
#            (the distro ships 3.12; the project pins 3.14 in .python-version),
#            so Python is never the user's problem and an apt upgrade cannot
#            break the interpreter under the venv.
#   node   — NodeSource 20.x. The frontend needs ≥20 (Vite 7) and the distro's
#            nodejs is 18, while node is a RUNTIME dependency in BOTH frontend
#            modes — the launcher runs `npx vite` / `npx vite preview`.
#   .env   — copied from .env.example when absent. NEVER overwritten.
#   deps   — `uv sync` (backend + root workspace) and `npm ci` (frontend).
#
# WHAT IT DELIBERATELY DOES NOT DO: start anything (that is `start`), and
# provision Exa — Exa ships present-but-inactive, activation is the user's
# decision, and the Hermes runtime arrives with that decision, not before it.
#
# Every step is idempotent (re-running reports "present" and moves on) and every
# step VERIFIES its own result instead of trusting an exit code.
# =============================================================================

NODE_MAJOR_MIN=20
UV_INSTALL_URL="https://astral.sh/uv/install.sh"
NODE_SETUP_URL="https://deb.nodesource.com/setup_${NODE_MAJOR_MIN}.x"

install_have() {
    command -v "$1" >/dev/null 2>&1
}

# sudo only when we are not already root — so the installer also works as root
# in a container or a test VM without inventing a `sudo` that does not exist.
install_as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

install_node_ok() {
    install_have node || return 1
    local major
    major="$(node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
    case "$major" in ''|*[!0-9]*) return 1 ;; esac
    [ "$major" -ge "$NODE_MAJOR_MIN" ]
}

# One step at a time, each named — so a failure says WHERE it stopped instead of
# leaving the user to read a wall of apt output.
install_step() {
    local label="$1"
    shift
    if ! "$@"; then
        log_error "Install stopped at: $label"
        return 1
    fi
}

install_preflight() {
    if ! install_have apt-get; then
        log_error "No apt-get found. This installer supports Debian, Ubuntu and Mint."
        return 1
    fi
    if ! install_have curl; then
        log_error "curl is missing. Install it first: sudo apt-get install -y curl"
        return 1
    fi
    return 0
}

install_git() {
    if install_have git; then
        log_success "git present ($(git --version | awk '{print $3}'))"
        return 0
    fi
    log_info "Installing git (apt)…"
    install_as_root apt-get update -qq
    install_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git
    if ! install_have git; then
        log_error "git is still missing after the apt install."
        return 1
    fi
    log_success "git installed ($(git --version | awk '{print $3}'))"
}

install_uv() {
    if install_have uv; then
        log_success "uv present ($(uv --version))"
        return 0
    fi
    log_info "Installing uv (astral installer, into ~/.local/bin)…"
    curl -LsSf "$UV_INSTALL_URL" | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! install_have uv; then
        log_error "uv is not on PATH after the install — expected $HOME/.local/bin/uv"
        return 1
    fi
    log_success "uv installed ($(uv --version)) to $HOME/.local/bin"
}

install_node() {
    if install_node_ok; then
        log_success "Node present ($(node --version))"
        return 0
    fi
    if install_have node; then
        log_warning "Node $(node --version) is older than ${NODE_MAJOR_MIN} — replacing it with NodeSource ${NODE_MAJOR_MIN}.x"
    fi
    log_info "Installing Node.js ${NODE_MAJOR_MIN}.x (NodeSource apt repo)…"
    curl -fsSL "$NODE_SETUP_URL" | install_as_root bash -
    install_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
    if ! install_node_ok; then
        log_error "Node.js >= ${NODE_MAJOR_MIN} is still missing (found: $(node --version 2>/dev/null || echo none))."
        return 1
    fi
    log_success "Node installed ($(node --version), npm $(npm --version))"
}

install_env_file() {
    if [ -f "$SCRIPT_DIR/.env" ]; then
        log_success ".env present (left untouched)"
        return 0
    fi
    if [ ! -f "$SCRIPT_DIR/.env.example" ]; then
        log_error ".env.example is missing — cannot create .env."
        return 1
    fi
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    log_success ".env created from .env.example (no keys set — the app starts without them)"
}

install_python_deps() {
    log_info "Syncing Python dependencies (uv sync; Python 3.14 is uv-managed)…"
    if ! ( cd "$SCRIPT_DIR" && uv sync ); then
        log_error "uv sync failed — see its output above."
        return 1
    fi
    local py="$SCRIPT_DIR/.venv/bin/python"
    if [ ! -x "$py" ]; then
        log_error "uv sync finished but $py does not exist."
        return 1
    fi
    log_success "Python dependencies installed ($("$py" --version 2>&1) in .venv)"
}

install_frontend_deps() {
    local lock="$FRONTEND_DIR/package-lock.json"
    local stamp="$FRONTEND_DIR/node_modules/.cogitate-lock.sha256"
    local want

    if [ ! -f "$lock" ]; then
        log_error "frontend/package-lock.json is missing — npm ci needs it."
        return 1
    fi

    # npm ci is a WIPE + reinstall, so an unconditional re-run costs minutes and
    # re-downloads everything. The stamp is the lockfile's hash, kept INSIDE
    # node_modules: derived state that cannot outlive the tree it describes, and
    # any edit to package-lock.json invalidates it by construction.
    want="$(sha256sum "$lock" | awk '{print $1}')"
    if [ -d "$FRONTEND_DIR/node_modules/vite" ] && [ -f "$stamp" ] \
        && [ "$(cat "$stamp" 2>/dev/null)" = "$want" ]; then
        log_success "Frontend dependencies present (package-lock.json unchanged)"
        return 0
    fi

    log_info "Installing frontend dependencies (npm ci)…"
    if ! ( cd "$FRONTEND_DIR" && npm ci --no-audit --no-fund ); then
        log_error "npm ci failed — see its output above."
        return 1
    fi
    if [ ! -d "$FRONTEND_DIR/node_modules/vite" ]; then
        log_error "npm ci finished but frontend/node_modules/vite is missing."
        return 1
    fi
    printf '%s' "$want" > "$stamp"
    local vite_ver
    vite_ver="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$FRONTEND_DIR/node_modules/vite/package.json" | head -1)"
    log_success "Frontend dependencies installed (vite ${vite_ver:-unknown})"
}

# THE POINT OF THE WHOLE SCRIPT: prove the install, do not assume it. Three
# checks that between them catch every way this can half-succeed — the wrong
# interpreter, a missing runtime dependency, a dead frontend toolchain.
install_verify() {
    local py="$SCRIPT_DIR/.venv/bin/python" out pinned

    pinned="$(tr -d '[:space:]' < "$SCRIPT_DIR/.python-version" 2>/dev/null)"
    if ! out="$("$py" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>&1)"; then
        log_error "Cannot run $py"
        printf '%s\n' "$out" | sed 's/^/    /'
        return 1
    fi
    if [ -n "$pinned" ] && [ "$out" != "$pinned" ]; then
        log_error "The venv runs Python $out but the project pins $pinned (.python-version)."
        return 1
    fi
    log_success "Interpreter check: Python $out in .venv"

    if ! out="$( cd "$BACKEND_DIR" && "$py" -c 'from app.main import app' 2>&1 )"; then
        log_error "The backend does not import — a runtime dependency is missing or broken:"
        printf '%s\n' "$out" | tail -15 | sed 's/^/    /'
        return 1
    fi
    log_success "Import check: app.main loads with every runtime dependency"

    if ! install_have node || ! install_have npm; then
        log_error "node/npm are not on PATH."
        return 1
    fi
    log_success "Toolchain check: node $(node --version), npm $(npm --version)"
}

cmd_install() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                📦 Installing Cogitate                    ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "  git and Node.js ${NODE_MAJOR_MIN} install system-wide via apt (it may ask for"
    echo "  your password). uv and Python 3.14 go to ~/.local. The project's own"
    echo "  dependencies go into .venv and frontend/node_modules. Nothing is started."
    echo ""

    # uv lives in ~/.local/bin. A fresh interactive shell has it on PATH via
    # ~/.profile, but a non-login shell does not — and without this a re-run
    # would not SEE the uv it installed last time and would reinstall it.
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) PATH="$HOME/.local/bin:$PATH"; export PATH ;;
    esac

    install_step "preflight"      install_preflight       || return 1
    install_step "git"            install_git             || return 1
    install_step "uv"             install_uv              || return 1
    install_step "node"           install_node            || return 1
    install_step ".env"           install_env_file        || return 1
    install_step "python deps"    install_python_deps     || return 1
    install_step "frontend deps"  install_frontend_deps   || return 1
    install_step "verification"   install_verify          || return 1

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                 ✅ Install complete                      ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Start it:   ./cogitate.sh start"
    echo "  Then open:  $FRONTEND_URL"
    echo ""
    echo "  No API keys are set. The app starts and runs without them; add a"
    echo "  provider key in Settings when you want a model to answer."
    echo ""
    echo "  Exa is included and INACTIVE. When you want it, see what it needs:"
    echo "    uv run python scripts/core/activate_exa.py"
    echo ""
    echo "  No model is chosen for you. What this machine could use:"
    echo "    uv run python scripts/core/setup_models.py"
    echo ""
    return 0
}

cmd_help() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║           🔧 Cogitate Development Manager                ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage: ./cogitate.sh <command>"
    echo ""
    echo "Commands:"
    echo "  install   - Install the toolchain and dependencies (run this first)"
    echo "  start     - Start all services (backend + frontend)"
    echo "  stop      - Stop all services gracefully"
    echo "  restart   - Stop then start all services"
    echo "  mode      - Switch the frontend: development | production"
    echo "  status    - Show service status and health"
    echo "  logs      - Show recent logs from all services"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./cogitate.sh start          # Start everything"
    echo "  ./cogitate.sh status         # Check what's running"
    echo "  ./cogitate.sh logs           # View recent logs"
    echo "  ./cogitate.sh restart        # Restart after code changes"
    echo "  ./cogitate.sh mode prod      # Serve the built bundle (faster UI)"
    echo "  ./cogitate.sh mode dev       # Back to the dev server"
    echo ""
    echo "URLs:"
    echo "  Frontend: $FRONTEND_URL"
    echo "  Backend:  $BACKEND_URL"
    echo "  API Docs: $BACKEND_URL/docs"
    echo ""
}

# =============================================================================
# Signal Handlers (for crash reporting)
# =============================================================================

setup_signal_handlers() {
    trap 'log_warning "SIGINT received"; cmd_stop; exit 130' INT
    trap 'log_warning "SIGTERM received"; cmd_stop; exit 143' TERM
}

# =============================================================================
# Main Entry Point
# =============================================================================

main() {
    setup_signal_handlers
    
    local command="${1:-help}"
    
    case "$command" in
        install)
            cmd_install
            ;;
        start)
            cmd_start
            ;;
        stop)
            cmd_stop
            ;;
        restart)
            cmd_restart
            ;;
        mode)
            cmd_mode "${2:-status}"
            ;;
        status)
            cmd_status
            ;;
        logs)
            cmd_logs
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

# Run main with all arguments
main "$@"
