#!/usr/bin/env python3
"""Capture screenshots of the running app, with every tooltip forced open if asked.

A README's screenshots go stale the day after they are taken unless the boring part is a script.
This drives a real Chromium over the DevTools Protocol: navigate a route, wait until the page has
actually rendered, optionally add `tooltip-open` to every `[data-tip]` element (DaisyUI's own
switch for it — the markup the UI already uses), then capture.

    python3 scripts/dev/capture_screenshots.py                       # the default pages, clean
    python3 scripts/dev/capture_screenshots.py --tooltips            # ... with every tooltip shown
    python3 scripts/dev/capture_screenshots.py --only dashboard,tools --base http://localhost:5173
    python3 scripts/dev/capture_screenshots.py --full                # whole page, not the viewport
    python3 scripts/dev/capture_screenshots.py --list                # what the default set is

Chromium is found on PATH (`chromium`, `google-chrome`, `chrome`), then in the Playwright cache.
WHY CDP rather than a screenshot-per-URL flag: `chrome --headless --screenshot` cannot run script in
the page, and the tooltip pass IS script. `websockets` is already present — `uvicorn[standard]`
depends on it — so this needs no new package.

A screenshot is a claim about what a user sees, so wait for the page rather than for the load event:
this app renders a shell instantly and fills it after its first API call, and a capture taken at
`load` is a picture of "Loading page...".
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = PROJECT_ROOT / "docs" / "screenshots"
SETTLE_SECONDS = 1.2

#: (slug, route, title) — the pages that answer "what do I get", in the order a visitor reads them.
PAGES: list[tuple[str, str, str]] = [
    ("dashboard", "/", "Dashboard"),
    ("agent-chat", "/agent-interaction", "Agent Chat"),
    ("agent-profiles", "/agent-profiles", "Agent Profiles"),
    ("tools", "/tools", "Tool Management"),
    ("workflows", "/workflow-templates", "Workflows"),
    ("exa", "/exa", "Exa Agent"),
    ("macros", "/macros", "Macros"),
    ("wiki", "/wiki", "Wiki"),
]

CHROME_CANDIDATES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "chrome",
)


class Cdp:
    """The handful of DevTools Protocol calls a screenshot needs — no dependency, no magic."""

    def __init__(self, ws_url: str) -> None:
        self._ws = connect(ws_url, max_size=None)
        self._id = 0

    def close(self) -> None:
        self._ws.close()

    def call(self, method: str, **params) -> dict:
        self._id += 1
        self._ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") != self._id:
                continue  # an event, not our answer
            if "error" in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg.get("result", {})

    def evaluate(self, expression: str):
        out = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        return out.get("result", {}).get("value")


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    for name in CHROME_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    cache = Path.home() / ".cache" / "ms-playwright"
    if cache.is_dir():
        for candidate in sorted(cache.glob("chromium-*/chrome-linux*/chrome"), reverse=True):
            return str(candidate)
    raise SystemExit(
        "No Chromium found. Pass --chrome PATH, or install one "
        "(the Playwright cache under ~/.cache/ms-playwright is searched automatically)."
    )


def _port_open(port: int, timeout: float = 0.2) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def launch_chrome(binary: str, width: int, height: int, scale: int) -> tuple[subprocess.Popen, int]:
    profile = tempfile.mkdtemp(prefix="cogitate-shots-")
    proc = subprocess.Popen(
        [
            binary,
            "--headless=new",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"--force-device-scale-factor={scale}",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-features=Translate",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    port_file = Path(profile) / "DevToolsActivePort"
    for _ in range(200):  # up to ~10 s
        if port_file.exists():
            port = int(port_file.read_text().splitlines()[0])
            if _port_open(port):
                return proc, port
        if proc.poll() is not None:
            raise SystemExit(f"Chromium exited immediately (code {proc.returncode})")
        time.sleep(0.05)
    proc.kill()
    raise SystemExit("Chromium never opened a DevTools port")


def page_target(port: int) -> str:
    """The ws URL of a page target — not the browser target, which cannot navigate."""
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
                targets = json.load(r)
        except OSError:
            time.sleep(0.1)
            continue
        for t in targets:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                return t["webSocketDebuggerUrl"]
        time.sleep(0.1)
    raise SystemExit("No page target appeared")


def wait_rendered(cdp: Cdp, route: str, timeout: float = 30.0) -> None:
    """Wait for the page to stop saying 'Loading page...' — the app's own loading shell.

    Not a fixed sleep: a slow first API call is exactly the case a screenshot script must survive,
    and a fixed sleep turns it into a picture of a spinner.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = cdp.evaluate("document.body ? document.body.innerText : ''") or ""
        busy = "Loading page..." in text or len(text.strip()) < 40
        if not busy:
            return
        time.sleep(0.25)
    print(f"  ! {route} still looked busy after {timeout:.0f}s — capturing anyway", file=sys.stderr)


def force_tooltips(cdp: Cdp, selector: str | None = None) -> int:
    """Show the tooltips. With `selector`, only those elements — forcing EVERY tip on a dense page
    stacks a hundred labels over the content, which reads as a broken layout rather than a feature."""
    expr = """((sel) => {
        const els = sel ? [...document.querySelectorAll(sel)] : [...document.querySelectorAll('[data-tip]')];
        els.forEach((el) => el.classList.add('tooltip-open'));
        return els.length;
    })(%s)""" % json.dumps(selector or "")
    return cdp.evaluate(expr) or 0


def tidy(cdp: Cdp) -> int:
    """Drop transient overlays — notification toasts and any open dialog.

    A screenshot is of the app, not of this machine's notification backlog: the toasts in the corner
    are whatever happened to fire while the developer was working, and they cover real UI.
    """
    return cdp.evaluate(
        """(() => {
            const toasts = [...document.querySelectorAll('.toast')];
            toasts.forEach((el) => el.remove());
            document.querySelectorAll('dialog[open]').forEach((d) => { try { d.close(); } catch (e) {} });
            return toasts.length;
        })()"""
    ) or 0


def looks_live(base: str) -> tuple[int, int]:
    """(sessions, agents) as the running app reports them — the guard against publishing a dev box.

    A screenshot is a picture of somebody's data. This machine's own database held real session
    titles ("Autophagy-Boosting Supplements…") and real agent names, and a capture from it went into
    a public repository before anyone looked. A demo install has none of that, so the count is the
    cheap tell: refuse to shoot a database that looks used unless the caller says --allow-live.

    Reads `total`, not the page: asking for a page_size the API rejects returns `{"detail": ...}`,
    and a len() over that reads as ZERO sessions — a guard that fails open is worse than no guard.
    An unreadable count raises.
    """
    def total(path: str, key: str) -> int:
        with urllib.request.urlopen(base.rstrip("/") + path, timeout=10) as r:
            data = json.load(r)
        if isinstance(data, dict) and isinstance(data.get("total"), int):
            return data["total"]
        items = data.get(key) if isinstance(data, dict) else data
        if isinstance(items, list):
            return len(items)
        raise ValueError(f"{path} answered without a count: {str(data)[:120]}")

    try:
        return total("/api/v1/sessions?page=1&page_size=1", "sessions"), total("/api/v1/agents", "agents")
    except Exception as exc:
        raise SystemExit(
            f"cannot read this install's session/agent count ({exc}) — refusing to capture blind.\n"
            "Point --base at the running app (a demo install, not a development box)."
        )


def capture(cdp: Cdp, out: Path, full: bool) -> None:
    if full:
        metrics = cdp.call("Page.getLayoutMetrics")
        size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
        params = {
            "clip": {
                "x": 0, "y": 0,
                "width": int(size.get("width") or 0),
                "height": int(size.get("height") or 0),
                "scale": 1,
            },
            "captureBeyondViewport": True,
        }
        if not params["clip"]["height"]:  # no metrics — the viewport is still a valid picture
            params = {}
    else:
        params = {}
    data = cdp.call("Page.captureScreenshot", format="png", **params)["data"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(data))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:5173", help="the running app (default: the dev server)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    ap.add_argument("--only", help="comma-separated slugs to capture (see --list)")
    ap.add_argument("--tooltips", action="store_true", help="show tooltips before capturing")
    ap.add_argument("--tips-selector", help="with --tooltips, only these elements (a CSS selector)")
    ap.add_argument("--full", action="store_true", help="capture the whole page, not the viewport")
    ap.add_argument("--raw", action="store_true", help="keep notification toasts and open dialogs")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--scale", type=int, default=2, help="device scale factor (2 = retina-crisp)")
    ap.add_argument("--chrome", help="path to a Chromium binary")
    ap.add_argument("--allow-live", action="store_true",
                    help="shoot a database that looks used (real sessions/agents) — think first")
    ap.add_argument("--list", action="store_true", help="print the default pages and exit")
    args = ap.parse_args()

    if args.list:
        for slug, route, title in PAGES:
            print(f"  {slug:<16} {route:<24} {title}")
        return 0

    wanted = {s.strip() for s in args.only.split(",")} if args.only else {p[0] for p in PAGES}
    unknown = wanted - {p[0] for p in PAGES}
    if unknown:
        raise SystemExit(f"unknown slug(s): {', '.join(sorted(unknown))} — try --list")

    outdir = Path(args.out)
    sessions, agents = looks_live(args.base)
    if not args.allow_live and (sessions > 2 or agents > 2):
        raise SystemExit(
            f"this install looks used ({sessions} sessions, {agents} agents) — a screenshot is a picture\n"
            "of somebody's data. Capture from a demo install instead (the target box is the one in sync\n"
            "with the repo), or pass --allow-live if you have looked at what is on screen."
        )
    print(f"install: {sessions} sessions, {agents} agents")
    binary = find_chrome(args.chrome)
    print(f"chromium: {binary}")

    proc, port = launch_chrome(binary, args.width, args.height, args.scale)
    try:
        cdp = Cdp(page_target(port))
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call(
            "Emulation.setDeviceMetricsOverride",
            width=args.width, height=args.height, deviceScaleFactor=args.scale, mobile=False,
        )
        for slug, route, title in PAGES:
            if slug not in wanted:
                continue
            url = args.base.rstrip("/") + route
            cdp.call("Page.navigate", url=url)
            wait_rendered(cdp, route)
            time.sleep(SETTLE_SECONDS)  # let the last fetch paint
            dropped = 0 if args.raw else tidy(cdp)
            tips = force_tooltips(cdp, args.tips_selector) if args.tooltips else 0
            suffix = "-tooltips" if args.tooltips else ""
            out = outdir / f"{slug}{suffix}.png"
            capture(cdp, out, args.full)
            extra = f", {tips} tooltips" if args.tooltips else ""
            if dropped:
                extra += f", {dropped} toast(s) dropped"
            print(f"  {title:<18} {route:<24} -> {out.relative_to(PROJECT_ROOT) if out.is_relative_to(PROJECT_ROOT) else out}{extra}")
    finally:
        proc.kill()
        proc.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
