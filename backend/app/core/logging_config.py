"""
Logging configuration.

Sets up console and file handlers with appropriate formatters
for development and production environments.
"""

import logging
import logging.handlers
import sys

from app.core.config import get_settings

settings = get_settings()


#: The attributes every LogRecord carries. Anything ELSE on a record was
#: attached by the caller through `extra=`. A format string of `%(message)s` alone
#: would carry that context and then DISCARD it.
_STANDARD_RECORD_FIELDS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None))
) | {"message", "asctime", "taskName"}


class ExtraAwareFormatter(logging.Formatter):
    """A formatter that PRINTS the `extra=` fields instead of throwing them away.

    WHY THE EXTRA FIELDS MATTER. `log_stream_open_failure` attaches
    `error`, `error_type` and `traceback` through `extra=`, and the format string
    rendered only `%(message)s` — so the line in `app.log` read

        ❌ LLM STREAM FAILED TO OPEN

    with nothing after it — **the cause captured and then discarded**, so the one
    record that knew why a stream failed cannot be diagnosed from the log.

    Rendering rules, chosen so a reader can still scan the file:
      - a single-line value is appended inline as `key=value`;
      - a MULTI-LINE value (a traceback) keeps its own lines, indented, rather
        than being flattened into one enormous line.

    It must never raise: a formatter that throws turns a logged failure into a
    logging failure, which is strictly worse than the missing detail.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        # `super().format()` has ALREADY appended the exception when the caller
        # passed `exc_info=True`. Several sites pass BOTH `exc_info=True` and a
        # `traceback` extra, which rendered the same stack twice — doubling the
        # length of every failure in a file that is already large. The extra is
        # therefore skipped when the base formatter has printed it.
        already_rendered = record.exc_info is not None

        extras = [
            (key, value)
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_FIELDS
            and not key.startswith("_")
            and not (already_rendered and key == "traceback")
        ]
        if not extras:
            return base

        inline: list[str] = []
        blocks: list[str] = []
        for key, value in extras:
            try:
                text = str(value)
            except Exception:  # noqa: BLE001 — never let a format kill a log
                text = "<unprintable>"
            if "\n" in text:
                blocks.append(
                    "\n".join(f"    {line}" for line in text.splitlines())
                )
            else:
                inline.append(f"{key}={text}")

        out = base
        if inline:
            out += " | " + " ".join(inline)
        for block in blocks:
            out += "\n" + block
        return out


def setup_logging() -> None:
    """
    Configure application logging.

    Sets up:
        - Console handler with colored output (development)
        - File handler with JSON-like format
        - Root logger with appropriate level
    """
    # THE LOG FOLLOWS THE ROOT (2026-09-12). The path is resolved through
    # `Paths`, not from the raw setting: `Paths` derives the installation root
    # from the shared database, so a test that aims DATABASE_URL at a temporary
    # directory gets its logs there too. Reading `settings.log_file` directly
    # made the log the ONE path that escaped that — a hardcoded path, which is
    # the exact defect `Paths` exists to remove.
    #
    # `settings.log_file` remains the declared default and the human-readable
    # value of record; the resolved path is what is actually opened, and it is
    # what gets logged.
    from app.core.config import Paths

    log_path = Paths.from_settings(settings).logs_dir / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter — ExtraAware, so `extra=` context is not discarded.
    formatter = ExtraAwareFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ONE level setting governs everything.
    #
    # These two handlers used to carry HARDCODED levels — DEBUG on the console,
    # INFO on the file — so `settings.log_level` only ever moved the ROOT logger.
    # That is a config which looks like it controls logging and does not: with
    # log_level=WARNING the console still emitted anything a child logger chose to
    # pass up, and the file still wrote INFO.
    #
    # The size difference made it visible in one run: 144 MB written to
    # console.log (the stdout capture, DEBUG) against 7.6 MB to app.log (INFO+).
    # The capture is rotated only at START — the file is held open by a shell
    # redirect while the app runs, so it cannot be rotated mid-session — which
    # means a too-low level grows it without bound until the next clean start.
    handler_level = getattr(logging, settings.log_level.upper())

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(handler_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler — rotating (10MB x 5 backups; prevents unbounded
    # growth — console.log/app.log once reached 66M/30M unbounded)
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_path),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setLevel(handler_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Log configuration
    logging.info("Logging configured: level=%s, file=%s", settings.log_level, log_path)
