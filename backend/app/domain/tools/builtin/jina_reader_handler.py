"""
Jina Reader Tool Handler.

Fetches any URL and converts it to LLM-friendly markdown.
No API key required - uses the free r.jina.ai endpoint.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

# Jina Reader endpoint
JINA_READER_URL = "https://r.jina.ai/"

# ── THE TOOL CONTRACT (2026-10-13, the research-run arc) ──────────────────────────────
# What a fetched page is allowed to cost, and when a page is worth nothing.
#
# Measured: 989 fetches over ~7 weeks, median 15,058 characters, p90 62,411, max 463,980 —
# and the fat ones are almost all navigation, boilerplate and repeated furniture around a
# short list of headlines. One page (wowt.com, 60,950 chars) is by itself ~15,000 tokens,
# which is the app's whole declared input budget for a single source.
#
# The cap keeps the HEAD and the TAIL (a page's footer often carries the byline and the date)
# and says so in the middle, so the model knows what it is not seeing and can ask narrower.
DEFAULT_MAX_CHARS = 24_000        # ~6,000 tokens; covers the median fetch whole
TAIL_CHARS = 4_000                # the end of a page, kept because the furniture is boring
CONFIG_MAX_CHARS = "max_chars"    # an admin can raise it per tool config

# The verdict: a body that carries nothing. The reader's own preamble (Title/URL Source/
# Markdown Content) is not content, so the check runs on what FOLLOWS it.
#
# 80 characters, not 200: the first cut of this check used 200 and refused a legitimate short
# page (152 characters of ordinary text) — an existing test caught it. An empty or near-empty
# body is what this catches; the MARKERS below catch a page that is long but says it has
# nothing, so the size threshold does not have to be brave.
USABLE_BODY_CHARS = 80
JUNK_SCAN_CHARS = 300
JUNK_MARKERS = (
    "page unavailable",
    "page not found",
    "access denied",
    "captcha",
    "are you a robot",
    "enable javascript",
    "1x1 image",
    "tracking pixel",
)



def _preamble_warning(content: str) -> str | None:
    """The reader's own `Warning:` line, if it wrote one.

    In markdown mode Jina emits a `Key: value` preamble before
    `Markdown Content:`. A `Warning:` line there is the SERVICE telling us the
    page may not be what it looks like — a cached snapshot, a partial render —
    and in markdown mode it is the only place that fact appears. A line after
    the content marker is page text, not a warning.
    """
    head = content[:2000]
    marker = head.find("Markdown Content:")
    if marker != -1:
        head = head[:marker]
    for line in head.splitlines():
        if line.strip().lower().startswith("warning:"):
            return line.split(":", 1)[1].strip()
    return None


def _declared_length(response: object) -> int | None:
    """What the service SAYS it sent, in bytes.

    `x-decompressed-content-length` is the markdown length; `content-length` is
    the wire length (compressed if we asked for gzip, which httpx does by
    default). Prefer the decompressed figure — it is the one comparable to the
    content we hold.
    """
    headers = getattr(response, "headers", {}) or {}
    for key in ("x-decompressed-content-length", "content-length"):
        raw = headers.get(key)
        if raw and str(raw).isdigit():
            return int(raw)
    return None


def _body_after_preamble(content: str) -> str:
    """The page's own text, with the reader's `Title:/URL Source:/Markdown Content:` block cut.

    The preamble is the READER describing the page, not the page — measuring it as content is
    how a 142-character tracking pixel passed a 50-character "empty" test.
    """
    marker = content.find("Markdown Content:")
    return content[marker + len("Markdown Content:"):] if marker != -1 else content


def _unusable_reason(content: str) -> str | None:
    """Why this body carries nothing — or None when it is worth the model's attention.

    Two shapes, both measured live: a body that is essentially empty once the reader's
    preamble is removed (a 1x1 tracking pixel, 142 characters), and a body that is large but
    says it has no content ("Page unavailable" — 137,930 characters, fetched and re-billed by
    the turn that followed).
    """
    body = _body_after_preamble(content).strip()
    head = body[:JUNK_SCAN_CHARS].lower()
    for marker in JUNK_MARKERS:
        if marker in head:
            return f"the page says '{marker}'"
    if len(body) < USABLE_BODY_CHARS:
        return f"only {len(body)} characters of content after the page's own header"
    return None


def _capped(content: str, max_chars: int) -> tuple[str, bool]:
    """The content as the model receives it, and whether anything was withheld.

    Head AND tail, with a notice in the middle naming the true size — an unannounced
    truncation is the kind of silent lie this codebase keeps paying for, and a caller who
    needs the whole page must be able to tell.
    """
    if max_chars <= 0 or len(content) <= max_chars:
        return content, False
    tail = min(TAIL_CHARS, max_chars // 2)
    head = content[: max_chars - tail]
    notice = (
        f"\n\n[… truncated by jina_reader: {len(content):,} characters in total, showing the "
        f"first {len(head):,} and the last {tail:,}. This page is mostly navigation and "
        f"boilerplate around its headlines — if what you need is not here, fetch a NARROWER "
        f"url (the article itself, from a search result) rather than this front page. …]\n\n"
    )
    return head + notice + content[-tail:], True


def _notebook_record(base_path: str, url: str) -> Dict[str, Any] | None:
    """What the agent's notebook remembers about this URL — or None (no notebook, or too old).

    Every failure here means "just fetch it": a notebook that cannot be read must never stop a
    fetch, so the lookup is silent about its own trouble and the fetch goes ahead.
    """
    if not base_path:
        return None
    try:
        from app.domain.agents.assignments import AssignmentStore

        return AssignmentStore(base_dir=base_path).recent_fetch(url)
    except Exception:
        logger.debug("jina: notebook lookup skipped for %s", url, exc_info=True)
        return None


class JinaReaderTool:
    """
    Jina Reader tool for fetching and cleaning web pages.

    Tags:
        - op:read
        - op:fetch
        - purpose:research
        - source:web
        - safe
        - text

    Operations:
        - fetch: Fetch a URL and return clean markdown content

    Features:
        - No API key required
        - Converts HTML to clean markdown
        - Handles JavaScript-rendered pages
        - Returns raw text or markdown
    """

    name = "Jina Reader"
    slug = "jina_reader"
    capability = "web-fetch"
    # THE FRESHNESS DEDUPE needs the agent's own folder: the handler asks the notebook whether
    # this URL was fetched recently, and answers from the record instead of pulling the page
    # again. (Measured: three live runs of one request re-fetched the same three URLs every
    # time — 117,352 characters, the whole turn's cost — 11 minutes apart on the third.)
    needs_workspace = True
    description = "Fetch a WEB URL (http/https) and convert it to LLM-friendly markdown (no API key needed) — local file:// paths need file-manager/doc-reader instead. A URL you fetched recently is served from your notebook instead of the web (pass refresh=true for a genuinely new copy). The reader may return a CACHED or PARTIALLY RENDERED page, so check the result's `warning` and compare `content_length` with `declared_length` before trusting data you depend on"
    tags = [
        "op:read",
        "op:fetch",
        "purpose:research",
        "source:web",
        "safe",
        "text",
    ]
    icon = "globe"
    color = "#4F46E5"  # Indigo

    config_schema = {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["markdown", "text"],
                "default": "markdown",
                "description": "Output format: 'markdown' (clean) or 'text' (plain)",
            },
        },
        "required": [],
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The WEB URL (http/https) to fetch — local file:// paths fail (use file-manager/doc-reader for local files)",
            },
            "refresh": {
                "type": "boolean",
                "description": "true = fetch a genuinely new copy even if your notebook recorded this URL recently (for a page that changes, like a news front page). False (default) = a fetch inside the freshness window is answered from your notebook.",
            },
        },
        "required": ["url"],
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Fetch a URL and return clean markdown content via Jina Reader.

        Args:
            config: Tool configuration (format: markdown/text)
            **kwargs: Fetch parameters (url)

        Returns:
            Dictionary with success status and page content
        """
        url = kwargs.get("url", "").strip()
        if not url:
            logger.warning("Jina Reader tool called with empty URL")
            return {
                "success": False,
                "error": "No URL provided. Please specify a URL to fetch.",
                "error_type": "ValidationError",
                "user_message": "Please provide a URL to fetch.",
            }

        # THE SCHEME GUARD (2026-08-24, QW5): r.jina.ai is a WEB
        # fetcher — a file:// path makes the remote service 400 and
        # wastes the call. Local files belong to file-manager /
        # doc-reader. Fail loudly + point the agent at the right tool.
        lowered = url.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            logger.warning("Jina Reader rejected non-web URL scheme: %s", url[:80])
            return {
                "success": False,
                "error": f"jina_reader fetches WEB URLs only (http/https) — '{url[:60]}' is not a web URL. Local files need the file-manager or doc-reader tools.",
                "error_type": "ValidationError",
                "user_message": "That path is a local file — jina_reader fetches web pages only. Use the file tools for local files.",
            }

        # Get format preference
        output_format = kwargs.get("format", config.get("format", "markdown"))

        # THE FRESHNESS DEDUPE (2026-10-13). Before the page is pulled, ask the notebook.
        # Measured: three live runs of ONE request re-fetched the same three URLs every time —
        # 117,352 characters, the whole turn's cost — the third of them 11 minutes after the
        # second. The prompt could not stop it (it named the sources and never said when they
        # were taken), so the check lives HERE, where it does not depend on the model reading a
        # list. It is a DEFAULT, not a refusal: `refresh=true` fetches anyway, and nothing about
        # a notebook can stop a fetch.
        refresh = bool(kwargs.get("refresh"))
        if not refresh:
            remembered = _notebook_record(str(config.get("base_path") or ""), url)
            if remembered:
                logger.info(
                    "📓 NOTEBOOK: served '%s' from the notebook (%s, %d chars) — no fetch",
                    url, remembered.get("age"), remembered.get("chars") or 0,
                )
                return {
                    "success": True,
                    "url": url,
                    "cached": True,
                    "fetched_at": remembered.get("at"),
                    "age": remembered.get("age"),
                    # NOT `chars`/`content`: this result is the notebook's record, not a fetch,
                    # and the capture hook keys on those fields (a served answer must not be
                    # recorded as a second fetch of the same page).
                    "content_length": remembered.get("chars") or 0,
                    "title": remembered.get("title") or "",
                    "excerpt": remembered.get("excerpt") or "",
                    "notebook": {
                        "assignment": remembered.get("assignment"),
                        "goal": remembered.get("goal"),
                        "notes": remembered.get("notes") or [],
                    },
                    "user_message": (
                        f"Already in your notebook: {url} was fetched {remembered.get('age')}. "
                        "What you learned from it is in `notebook.notes` — write from that. Pass "
                        "refresh=true if you need a genuinely new copy."
                    ),
                }

        logger.info(f"Jina Reader: fetching '{url}' (format={output_format})")

        try:
            headers = {
                "Accept": "text/plain" if output_format == "text" else "text/markdown",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{JINA_READER_URL}{url}",
                    headers=headers,
                    follow_redirects=True,
                )
                response.raise_for_status()
                content = response.text

            if not content or len(content.strip()) < 50:
                return {
                    "success": False,
                    "error": f"Page returned very little content ({len(content)} characters). The page may be empty or blocked.",
                    "error_type": "EmptyContent",
                    "user_message": "The page had very little content. Try a different URL.",
                    "url": url,
                }

            # THE VERDICT (2026-10-13): a body that carries nothing is refused before it is
            # billed. The reader's own preamble does not count as content, and a page that SAYS
            # it has none ('Page unavailable', a 1x1 tracking pixel) is not a source — so no
            # content is returned and the notebook never records it as one.
            unusable = _unusable_reason(content)
            if unusable:
                logger.warning("Jina Reader: UNUSABLE '%s' — %s", url, unusable)
                return {
                    "success": False,
                    "url": url,
                    "error": f"'{url}' came back with nothing usable: {unusable}.",
                    "error_type": "UnusableContent",
                    "content_length": len(content),
                    "user_message": (
                        f"That page had nothing usable ({unusable}). Try a different, more "
                        "specific URL — a front page that blocks readers is worth skipping."
                    ),
                }

            # THE CAP: what the model is allowed to receive from one page. The notice in the
            # middle keeps the truncation HONEST — the model can see what it is missing and ask
            # narrower (a 60,950-character front page is ~15,000 tokens of mostly furniture).
            max_chars = config.get(CONFIG_MAX_CHARS) or DEFAULT_MAX_CHARS
            try:
                max_chars = int(max_chars)
            except (TypeError, ValueError):
                max_chars = DEFAULT_MAX_CHARS
            shown, truncated = _capped(content, max_chars)

            result = {
                "success": True,
                "url": url,
                "content": shown,
                "content_length": len(content),
            }
            if truncated:
                result["truncated"] = True
                result["shown_length"] = len(shown)
                logger.info(
                    "Jina Reader: capped '%s' to %d of %d characters (the model is told)",
                    url, len(shown), len(content),
                )

            # THE READER'S OWN SIGNALS, SURFACED RATHER THAN DISCARDED
            # (2026-09-26). The service already tells a caller enough to detect
            # a cached or partial page — a declared length in the headers and a
            # `Warning:` line in the body — and this handler used to keep only
            # `content`, so a truncated fetch came back as an unqualified
            # SUCCESS (Bob's weather.com report, 2026-09-16).
            declared = _declared_length(response)
            if declared is not None:
                result["declared_length"] = declared
                received = len(content.encode("utf-8"))
                if received != declared:
                    # NOT a failure — a mismatch to surface. The page may be
                    # partial, or the service may count differently; either way
                    # the caller can now see the disagreement.
                    logger.warning(
                        "Jina Reader: declared %d bytes but received %d for '%s' "
                        "— the page may be partial",
                        declared, received, url,
                    )
                    result["length_mismatch"] = received - declared

            usage_tokens = response.headers.get("x-usage-tokens")
            if usage_tokens and str(usage_tokens).isdigit():
                result["usage_tokens"] = int(usage_tokens)

            warning = _preamble_warning(content)
            if warning:
                result["warning"] = warning
                logger.warning("Jina Reader: the service warned on '%s': %s", url, warning)

            logger.info(
                f"Jina Reader: fetched '{url}' ({len(content)} chars"
                + (f", declared {declared}" if declared is not None else "")
                + (", with a service warning" if warning else "") + ")"
            )
            return result

        except httpx.TimeoutException:
            logger.warning(f"Jina Reader: timeout fetching '{url}'")
            return {
                "success": False,
                "error": f"Timeout fetching '{url}'. The page may be slow or unreachable.",
                "error_type": "TimeoutError",
                "user_message": "The page took too long to respond. Try again or use a different URL.",
            }
        except httpx.HTTPStatusError as e:
            logger.warning(f"Jina Reader: HTTP {e.response.status_code} for '{url}'")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code} error fetching '{url}'.",
                "error_type": "HTTPError",
                "user_message": f"Could not fetch the page (error {e.response.status_code}). Try a different URL.",
            }
        except httpx.RequestError as e:
            logger.error(f"Jina Reader: request error for '{url}': {e}")
            return {
                "success": False,
                "error": f"Network error fetching '{url}': {str(e)}",
                "error_type": "NetworkError",
                "user_message": "A network error occurred. Please try again.",
            }
        except Exception as e:
            logger.error(f"Jina Reader: unexpected error for '{url}': {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "UnknownError",
                "user_message": "An unexpected error occurred while fetching the page.",
            }
