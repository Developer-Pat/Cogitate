"""Langfuse observability for the workflows and chat surfaces — the **v4** surface.

The installed SDK is v4, and v4 has no ``client.trace()``, no ``trace.span()`` and no
``trace.generation()``. An observation is opened with ``start_observation`` /
``start_as_current_observation``, a child comes off the returned handle (or from an explicit
``trace_context``), and the terminal values are attached with ``update(...)`` **before**
``end()`` — v4's ``end(*, end_time=None)`` accepts nothing else.

Three measured facts shape everything below:

* **The trace id is derivable, not fetchable.** ``create_trace_id(seed)`` returns
  ``sha256(seed)[:32]`` — the same 32 lowercase hex characters the SDK's own
  ``create_trace_id(seed=...)`` produces, computable with no client, no keys and no network. So
  both sides of a seam can name the same trace without asking anyone.
* **A trace's attributes ride its spans.** ``session_id`` / ``user_id`` / ``trace_name`` are set by
  entering ``propagate_attributes(...)`` (which applies them to the current span *and* to every span
  created inside it), or — for a LangGraph run — by the reserved ``langfuse_*`` keys in the run
  config's ``metadata``, which the callback handler parses.
* **Nothing here may be fatal.** Every verb degrades to a no-op when tracing is off, and each one
  catches its own failure: a tracing fault must never change a request's outcome.

Setup — the keys are the SDK's own, and the switch is the SDK's own:

    LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY   required for tracing
    LANGFUSE_BASE_URL                          optional, the destination
                                               (LANGFUSE_HOST is the DEPRECATED alias — still read,
                                               second, so an older .env keeps working)
    LANGFUSE_TRACING_ENVIRONMENT               optional, production | staging | development
    LANGFUSE_TRACING_ENABLED                   optional, "false" to switch tracing off

Usage — one trace per unit of work, its id derived from the unit's own id:

    trace_id = LangfuseManager.create_trace_id(f"chat:{session_id}:{turn}")
    with LangfuseManager.create_trace("agent-chat", session_id=session_id, trace_id=trace_id) as span:
        ...                     # every observation created in here joins this trace
        LangfuseManager.update(span, output={"status": "completed"})

and for a LangGraph run, the handler plus the run config's trace identity:

    handler = LangfuseManager.get_langfuse_handler(trace_id=trace_id)
    config = LangfuseManager.with_run_metadata(config, session_id=session_id, trace_name=name)
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import uuid
from contextlib import ExitStack, contextmanager
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

# Langfuse requires a trace id to be exactly 32 lowercase hex characters.
_TRACE_ID_LENGTH = 32

# The SDK's own default destination. Needed because this adapter passes the value EXPLICITLY
# (see the docstring): the SDK's resolution is
# ``base_url or LANGFUSE_BASE_URL or host or LANGFUSE_HOST or default``, so a default handed in
# here wins over every variable the SDK would otherwise have read.
_DEFAULT_BASE_URL = "https://cloud.langfuse.com"

# The reserved keys the v4 LangChain callback handler reads off a run's config metadata.
_SESSION_KEY = "langfuse_session_id"
_USER_KEY = "langfuse_user_id"
_TRACE_NAME_KEY = "langfuse_trace_name"
_TAGS_KEY = "langfuse_tags"


def _setting(name: str) -> Optional[str]:
    """An integration setting by this app's own convention: the ``Settings`` field, then the
    environment.

    Why both — and why Settings wins. ``Settings`` reads ``.env`` through pydantic's ``env_file``,
    which populates the model and not the environment. But the environment is **not** empty either:
    litellm calls ``load_dotenv()`` at import time, and the app imports litellm, so the whole
    ``.env`` is copied into ``os.environ`` by the time anything here runs. The two therefore agree
    in practice (same file), and this order keeps the declaration authoritative — a value that is
    only exported in a shell no longer silently outranks the one in ``.env``.

    A caller that redirects tracing (a diagnostic, a test) must clear the LANGFUSE_* family from
    the environment as well as stand in for Settings, or it will be overruled by the ``.env`` copy.
    """
    try:
        from app.core.config import get_settings

        value = getattr(get_settings(), name, None)
    except Exception:  # settings unavailable (a script, a test): the environment is still a source
        value = None
    if value is None or value == "":
        value = os.getenv(name.upper())
    return None if value in (None, "") else str(value)


def _base_url() -> str:
    """Where traces go: the SDK's CURRENT variable name first, its DEPRECATED alias second.

    ``LANGFUSE_HOST`` is documented as deprecated in favour of ``LANGFUSE_BASE_URL``, and both
    still resolve to the same client argument. Reading only the old name is the failure this
    exists to prevent: an installation on a regional host (``us.``/``eu.`` cloud, or self-hosted)
    puts its URL in the new variable, the adapter's default silently replaced it, and every trace
    was posted to the wrong host — with the keys for the right one.
    """
    return _setting("langfuse_base_url") or _setting("langfuse_host") or _DEFAULT_BASE_URL


class LangfuseManager:
    """The one seam between the app and the SDK.

    A single injectable client (``_client``) is held so a test can hand in a ``Langfuse`` built with
    an in-memory span exporter. That matters: the callback handler resolves the same per-project
    resource manager the client registered, so the exported spans are a genuine offline witness of
    what the app sent — no keys and no network.
    """

    _client = None

    # ── Configuration ────────────────────────────────────────────────────────

    @classmethod
    def is_enabled(cls) -> bool:
        """Keys present, and the switch not off.

        ``LANGFUSE_TRACING_ENABLED`` is the SDK's own switch name — if the SDK honours a switch the
        app must read the same one, or the two disagree in both directions. It is read here (from
        Settings or the environment) and passed to the SDK explicitly when the client is built, so
        there is exactly one resolution.
        """
        switch = (_setting("langfuse_tracing_enabled") or "true").strip().lower()
        if switch in {"false", "0", "no"}:
            return False
        return bool(_setting("langfuse_public_key") and _setting("langfuse_secret_key"))

    @staticmethod
    def create_trace_id(seed: str | None) -> str:
        """The trace id for ``seed``: ``sha256(seed)[:32]``.

        Identical to the SDK's ``create_trace_id(seed=...)`` and **pure** — which is the point. The
        app can name the trace it *would* have sent even with tracing off, and a workflow run's node
        spans and the app's own run record are joined by an id neither side had to look up.

        A missing seed is a programming error, not a case: the SDK reads a falsy seed as "no seed"
        and generates a random id, and mirroring that is the safe half of the mirror — hashing the
        empty string would hand every seedless caller the **same** id, so their traces would silently
        collapse into one.
        """
        if not seed:
            logger.warning("langfuse: create_trace_id called without a seed — using a random id")
            return uuid.uuid4().hex
        return hashlib.sha256(seed.encode()).hexdigest()[:_TRACE_ID_LENGTH]

    @classmethod
    def run_trace_id(cls, workflow_id: str) -> str:
        """The trace id for a workflow **run**.

        ONE derivation, so the run's own spans, the run record and the debug endpoint cannot drift
        apart: they all ask this. A retry reuses it, deliberately — a retried run is the same run
        (`execute_with_retry` re-invokes the same `workflow_id`), and its attempts belong on one
        trace rather than scattered across several.
        """
        return cls.create_trace_id(f"workflow:{workflow_id}")

    @classmethod
    def chat_trace_id(cls, session_id: Any, turn: Any) -> str:
        """The trace id for one chat turn — the same one-derivation rule as a run's."""
        return cls.create_trace_id(f"chat:{session_id}:{turn}")

    @classmethod
    def get_client(cls):
        """The Langfuse client, or ``None`` when tracing is off or construction failed.

        Deliberately lazy and **without ``auth_check()``**: that is a network round trip in a getter,
        so a flaky link silently disabled tracing and every request paid for the retry.
        """
        if not cls.is_enabled():
            return None

        if cls._client is None:
            try:
                from langfuse import Langfuse

                cls._client = Langfuse(
                    public_key=_setting("langfuse_public_key"),
                    secret_key=_setting("langfuse_secret_key"),
                    base_url=_base_url(),
                    # The environment splits test traces from production ones in the UI and in every
                    # dashboard built on it. Left unset the SDK tags everything "default", which is
                    # the one value that cannot be filtered apart later.
                    environment=_setting("langfuse_environment") or "development",
                    # The switch is resolved in `is_enabled()`, ABOVE — passing it makes that
                    # resolution authoritative, so the SDK can never trace while the app thinks
                    # tracing is off (or the reverse).
                    tracing_enabled=True,
                )
            except Exception as exc:  # construction is the one place a failure is recoverable
                logger.warning("langfuse: client construction failed — tracing is off | %s", exc)
                return None

        return cls._client

    # ── The trace root ───────────────────────────────────────────────────────

    @classmethod
    @contextmanager
    def create_trace(
        cls,
        name: str,
        *,
        session_id: Optional[str | int] = None,
        user_id: Optional[str | int] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        input: Any = None,
    ) -> Iterator[Any]:
        """Open the trace's root span and **always** close it. Yields the handle, or ``None``.

        Yielding ``None`` when tracing is off is what lets a caller write one code path instead of
        two. The trace's attributes are applied by entering ``propagate_attributes`` inside, so every
        observation created in the block inherits them, and the span is ended on the way out — an
        abandoned stream still closes its span.

        ``trace_id`` comes from ``create_trace_id`` so the trace can be named by whoever needs it.
        """
        opened = cls._open_root(
            name,
            session_id=session_id,
            user_id=user_id,
            trace_id=trace_id,
            metadata=metadata,
            input=input,
        )
        if opened is None:
            yield None
            return

        stack, observation = opened
        try:
            yield observation
        finally:
            stack.close()

    @classmethod
    def _open_root(
        cls,
        name: str,
        *,
        session_id: Optional[str | int],
        user_id: Optional[str | int],
        trace_id: Optional[str],
        metadata: Optional[dict],
        input: Any,
    ):
        """Build the root observation behind an ``ExitStack``, or ``None``. Never raises."""
        client = cls.get_client()
        if client is None:
            return None
        try:
            from langfuse import propagate_attributes

            stack = ExitStack()
            try:
                observation = stack.enter_context(
                    client.start_as_current_observation(
                        name=name,
                        as_type="span",
                        trace_context={"trace_id": trace_id} if trace_id else None,
                        input=input,
                        metadata=metadata or None,
                    )
                )
                if session_id or user_id:
                    # THE SDK TAKES STRINGS AND DROPS ANYTHING ELSE, silently: an int session id
                    # (which is what this app's chat route holds — `session_id: int | None`) was
                    # discarded with a warning, so no chat trace ever carried its session. The
                    # coercion belongs here, at the one point where the SDK is spoken to, and it
                    # mirrors what `run_metadata` already does for the LangGraph path.
                    stack.enter_context(
                        propagate_attributes(
                            session_id=str(session_id) if session_id is not None else None,
                            user_id=str(user_id) if user_id is not None else None,
                            trace_name=name,
                        )
                    )
            except Exception:
                stack.close()
                raise
            return stack, observation
        except Exception as exc:
            logger.warning("langfuse: could not open the trace root %r | %s", name, exc)
            return None

    @classmethod
    def update(
        cls,
        observation: Any,
        *,
        output: Any = None,
        level: Optional[str] = None,
        status_message: Optional[str] = None,
        metadata: Optional[dict] = None,
        usage_details: Optional[dict] = None,
        cost_details: Optional[dict] = None,
    ) -> None:
        """Attach an observation's terminal values — the v4 idiom: ``update``, *then* ``end``.

        ``observation.end()`` takes only an end time, so handing it ``output=`` raises ``TypeError``.
        This is the one verb that carries them, and it is a no-op when ``observation`` is ``None``.

        ``usage_details`` is a generation's token counts, keyed by the usage type names its model
        definition declares — ``input`` / ``output`` for these providers.

        ``cost_details`` is THE APP'S OWN PRICE for the call, keyed the same way. Given it, Langfuse
        takes the number as the cost: no model definition is needed, so a local or private model is
        priced like any other and there is no second copy of the prices to keep in step. With it
        absent, cost falls back to whatever a model definition says — which is nothing for a model
        that has none, and the reason the app sends no cost at all for a price nobody publishes
        (a ``0.0`` would read as "this call was free").

        NOTE the conversion above is not decoration: passing these fields through a signature that
        does not name one raises ``TypeError`` AT THE CALL, before this body runs — so the
        ``except`` below cannot catch it and the caller sees a broken call rather than an untraced
        one. A test's fake that accepts ``**kwargs`` will not find that; only the real signature
        will (see ``test_generation_cost``).
        """
        if observation is None:
            return
        try:
            kwargs: dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = output
            if level is not None:
                kwargs["level"] = level
            if status_message is not None:
                kwargs["status_message"] = status_message
            if metadata is not None:
                kwargs["metadata"] = metadata
            if usage_details is not None:
                kwargs["usage_details"] = usage_details
            if cost_details is not None:
                kwargs["cost_details"] = cost_details
            if kwargs:
                observation.update(**kwargs)
        except Exception as exc:
            logger.warning("langfuse: update failed | %s", exc)

    # ── Model calls ──────────────────────────────────────────────────────────

    @classmethod
    def _inside_a_trace(cls) -> bool:
        """Whether an observation is open in this context.

        A ``generation`` with no open span becomes a trace of its own, which is not what "one trace
        per unit of work" means. The chat surface has one traced path (the turn) and calls that
        belong to no turn — ``chat_delegate``, the ``/completions`` passthrough — and those are the
        app's own accounting to keep, not traces to manufacture here.
        """
        try:
            from opentelemetry import trace as otel_trace

            return bool(otel_trace.get_current_span().get_span_context().is_valid)
        except Exception:  # the check must never be the thing that breaks a call
            return False

    @classmethod
    @contextmanager
    def generation(
        cls,
        *,
        name: str,
        model: Optional[str] = None,
        input: Any = None,
        metadata: Optional[dict] = None,
    ) -> Iterator[Any]:
        """One model call, as a ``generation`` hanging from the observation that is open.

        A **generation**, not a span: it is the observation type Langfuse prices and groups by model,
        and each invocation is its own unit — a retried call is a second generation, not a longer
        first one. The name should be the operation, stable and verb-first (``generate-response``),
        so dashboards and evaluators can target it.

        Yields ``None`` — making the caller's block a no-op — when tracing is off, when no span is
        open to hang it from, or when the SDK cannot build the observation. A failure that reaches
        the body is passed to the observation (so the generation is marked errored) and then
        re-raised: a tracing fault must never be what swallows a model error.
        """
        client = cls.get_client()
        if client is None or not cls._inside_a_trace():
            yield None
            return

        cm: Any = None
        try:
            cm = client.start_as_current_observation(
                as_type="generation",
                name=name,
                model=model,
                input=input,
                metadata=metadata or None,
            )
            observation = cm.__enter__()
        except Exception as exc:
            logger.warning("langfuse: could not open the generation %r | %s", name, exc)
            if cm is not None:
                try:
                    cm.__exit__(None, None, None)
                except Exception:
                    pass
            yield None
            return

        try:
            yield observation
        except BaseException as exc:
            # The call FAILED: say so on the observation BEFORE ending it. The level and the message
            # are what the UI and a filter read; an exception alone would leave the generation
            # looking like one that merely stopped.
            cls.update(observation, level="ERROR", status_message=str(exc)[:300])
            try:
                cm.__exit__(*sys.exc_info())
            except Exception as exc:
                logger.warning("langfuse: closing a failed generation raised | %s", exc)
            raise
        else:
            try:
                cm.__exit__(None, None, None)
            except Exception as exc:
                logger.warning("langfuse: closing the generation %r raised | %s", name, exc)


    # ── LangGraph runs ───────────────────────────────────────────────────────

    @classmethod
    def get_langfuse_handler(cls, trace_id: Optional[str] = None):
        """The LangChain/LangGraph callback handler, linked to ``trace_id`` — or ``None``.

        v4 links a handler through ``trace_context``. The old ``setattr(handler, "trace_id", ...)``
        set an attribute the handler never reads, so the link silently did nothing. Session, user and
        trace name reach the trace through the run config's reserved ``langfuse_*`` metadata keys —
        see ``with_run_metadata``.
        """
        client = cls.get_client()
        if client is None:
            return None

        try:
            from langfuse.langchain import CallbackHandler
        except ImportError as exc:
            logger.warning("langfuse: LangChain integration unavailable | %s", exc)
            return None

        try:
            return CallbackHandler(
                public_key=_setting("langfuse_public_key"),
                trace_context={"trace_id": trace_id} if trace_id else None,
            )
        except Exception as exc:
            logger.warning("langfuse: handler construction failed | %s", exc)
            return None

    @classmethod
    def run_metadata(
        cls,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        trace_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """The config-metadata keys that give a LangGraph run its trace identity.

        The handler parses exactly these names and applies them to the trace, so they land on the
        run's span *and* on every node span under it. Empty when tracing is off, which is what makes
        it safe to merge unconditionally.
        """
        if not cls.is_enabled():
            return {}
        metadata: dict[str, Any] = {}
        if session_id:
            metadata[_SESSION_KEY] = str(session_id)
        if user_id:
            metadata[_USER_KEY] = str(user_id)
        if trace_name:
            metadata[_TRACE_NAME_KEY] = str(trace_name)
        if tags:
            metadata[_TAGS_KEY] = [str(tag) for tag in tags]
        return metadata

    @classmethod
    def with_run_metadata(cls, config: dict, **kwargs: Any) -> dict:
        """``config`` with its ``metadata`` carrying the run's trace identity.

        The reserved key names stay in here: a call site should not have to know that the handler
        reads ``langfuse_session_id``. Returns ``config`` unchanged when tracing is off.
        """
        attributes = cls.run_metadata(**kwargs)
        if not attributes:
            return config
        metadata = dict(config.get("metadata") or {})
        metadata.update(attributes)
        return {**config, "metadata": metadata}

    # ── The UI link ──────────────────────────────────────────────────────────

    @classmethod
    def trace_url(cls, trace_id: str) -> Optional[str]:
        """The Langfuse UI link for ``trace_id``, or ``None``.

        ``client.get_trace_url()`` is **not** a string builder: it fetches (and then caches) the
        project id over the network, so it can raise. A URL is a convenience — a tracing fault must
        never turn a debug endpoint into a 500, and the id alone is still useful.
        """
        client = cls.get_client()
        if client is None:
            return None
        try:
            url = client.get_trace_url(trace_id=trace_id)
            return str(url) if url else None
        except Exception as exc:
            logger.warning("langfuse: trace url unavailable | %s", exc)
            return None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    @classmethod
    def flush(cls) -> None:
        """Flush pending observations (the SDK batches them on a background thread)."""
        if cls._client is not None:
            try:
                cls._client.flush()
            except Exception as exc:
                logger.warning("langfuse: flush failed | %s", exc)

    @classmethod
    def shutdown(cls) -> None:
        """Flush and release the client. Called on application shutdown."""
        if cls._client is not None:
            try:
                cls._client.flush()
                cls._client.shutdown()
            except Exception as exc:
                logger.warning("langfuse: shutdown failed | %s", exc)
            finally:
                cls._client = None
