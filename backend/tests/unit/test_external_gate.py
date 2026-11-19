"""
The EXTERNAL gate — the generic form of the tier.

THE EXTERNAL TRIAGE (Phase A2). The class is defined by a QUESTION —
*whose availability is it?* — and the answer must be "not ours". It was called
`live` and that name was the bug: it meant "Ollama", because a category named
after its first example stops being a category.

What is pinned here:

1. **The specific and the broad probe are NOT interchangeable.** That is the
   hard-won 2026-09-13 lesson (a configured DeepSeek key answered "available"
   for a test that needed Ollama EMBEDDINGS, so it ran and failed as though the
   code were broken). `external("ollama")` must fail when Ollama is down even
   though a remote key exists.

2. **An unregistered dependency name FAILS the test, it does not pass it.** A
   probe that answers for the wrong service is worse than no probe, so the gate
   refuses to guess. Without this, a typo in a marker name yields a test that
   always runs — and if the external call happens to be caught downstream,
   always passes, proving nothing.

3. **An unmarked test is untouched.** The gate must stay quiet for the ~160
   files that need nothing external; a gate that fires on everything is a gate
   that will be switched off.
"""

from __future__ import annotations

import pytest

from tests import conftest as cf


# ── the registry itself ─────────────────────────────────────────────────────


def test_the_known_dependencies_are_registered() -> None:
    assert {"ollama", "llama-cpp", "embeddings"} <= set(cf.EXTERNAL_PROBES)


def test_every_registered_dependency_has_a_label() -> None:
    """A skip must be actionable. 'external unavailable' tells a person nothing;
    'local Ollama is not reachable' tells them what to start."""
    for dep in cf.EXTERNAL_PROBES:
        assert dep in cf.DEPENDENCY_LABELS, f"{dep} has no label for its skip message"


def test_every_probe_is_callable_and_returns_a_bool() -> None:
    for dep, probe in cf.EXTERNAL_PROBES.items():
        result = probe()
        assert isinstance(result, bool), f"{dep} probe returned {type(result)}, not bool"


# ── the probe distinctions (the 2026-09-13 lesson, made explicit) ───────────


def test_the_ollama_probe_checks_OLLAMA_not_just_a_key(monkeypatch) -> None:
    """A configured remote key must NOT satisfy `ollama` — a remote chat key
    cannot embed, and that mismatch produced a test that ran and failed as
    though our code were broken."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "present-but-irrelevant")
    monkeypatch.setenv("OPENROUTER_API_KEY", "present-but-irrelevant")
    monkeypatch.setattr(cf, "_probe", lambda url, timeout=2.0: False)
    assert cf.EXTERNAL_PROBES["ollama"]() is False


def test_there_is_NO_generic_any_provider_key(monkeypatch) -> None:
    """THE REMOVED-KEY GUARD. A broad "some LLM is up" key was written and
    deleted: a test whose fixture pins `provider="ollama"` needs THAT daemon, so
    llama.cpp running would have answered "available" and the test would have
    run and failed. If someone re-adds a broad key, this fails and points at the
    reasoning."""
    assert "llm" not in cf.EXTERNAL_PROBES, (
        "a generic 'any provider' probe was re-added — see the registry comment: "
        "keys must name what a test actually needs"
    )


def test_a_configured_chat_key_does_NOT_satisfy_the_embeddings_need(monkeypatch) -> None:
    """The capability distinction: embeddings != chat. A remote CHAT key cannot
    embed, so it must not satisfy a test that needs embeddings — this is the
    2026-09-13 lesson kept alive in a test rather than only in a comment."""
    monkeypatch.setattr(cf, "_probe", lambda url, timeout=2.0: False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "a-chat-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "a-chat-key")
    assert cf.EXTERNAL_PROBES["embeddings"]() is False


# ── the gate's behaviour, driven through pytest itself ──────────────────────
# These are run as SUBPROCESSES in a temp dir, because the gate is an autouse
# fixture: the only honest way to test it is to run pytest against a file that
# uses the marker and read what it did.

_GATE_TEMPLATE = """
import pytest

{dep}

def test_the_marked_test():
    assert True
"""


def _run_gate(tmp_path, marker: str) -> tuple[int, str]:
    """Run one marked test through pytest and return (exit code, output)."""
    import shutil
    import subprocess
    import sys

    # Copy the real conftest so the gate under test is the REAL one.
    real = cf.__file__
    assert real is not None
    shutil.copy(real, tmp_path / "conftest.py")
    (tmp_path / "test_gate_probe.py").write_text(_GATE_TEMPLATE.format(dep=marker))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "test_gate_probe.py", "-q", "--no-header",
         "-p", "no:randomly", "-rs"],
        cwd=tmp_path, capture_output=True, text=True, timeout=180,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_an_unknown_dependency_name_FAILS_the_test(tmp_path) -> None:
    """THE POINT OF THE WHOLE MECHANISM. A misspelled dependency must not be a
    test that silently always runs — it must be a failure that names the fix."""
    code, out = _run_gate(tmp_path, '@pytest.mark.external("nonsense-service")')
    assert code != 0, "an unknown dependency must not pass"
    assert "Unknown external dependency" in out
    assert "EXTERNAL_PROBES" in out, "the failure must name where to register it"


def test_a_missing_dependency_SKIPS_with_a_named_reason(tmp_path, monkeypatch) -> None:
    """Absent dependency -> a VISIBLE skip naming what to start, never a failure
    that reads like a defect in our code."""
    code, out = _run_gate(tmp_path, '@pytest.mark.external("ollama")')
    # Ollama is deliberately stopped in this environment; if it is up the test
    # is vacuous, so say so rather than passing quietly.
    if "skipped" not in out and "passed" in out:
        pytest.skip("Ollama is reachable here — the skip path cannot be exercised")
    assert code == 0, "a skip must not fail the run"
    assert "skipped" in out
    assert "not reachable" in out


def test_a_TEST_IS_UNTOUCHED_WHEN_IT_DECLARES_NOTHING(tmp_path) -> None:
    """THE STAYS-QUIET CASE. ~160 files need nothing external; a gate that
    touches them would be switched off, taking the whole tier with it."""
    code, out = _run_gate(tmp_path, "")
    assert code == 0
    assert "passed" in out
    assert "skipped" not in out
    assert "not reachable" not in out


# ── the backend gate: the RUNNER's answer wins, and a probe tolerates load ──────────────


def test_the_runners_backend_answer_wins_without_probing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate must not re-decide what the pre-flight already measured.

    Under `-n auto` every worker ran its own probe inside the same second, so a healthy backend
    produced ten spurious skips on one run and none on the next — the ten always the
    `backend`-marked tests, while the runner's own header said "healthy". Reading the runner's
    answer removes both the disagreement and the load spike the probing itself caused.
    """

    def explode(*args, **kwargs):
        raise AssertionError("the gate probed the backend despite the runner's answer")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    monkeypatch.setenv("COGITATE_BACKEND_UP", "1")
    assert cf.resolve_backend_available() is True

    monkeypatch.setenv("COGITATE_BACKEND_UP", "0")
    assert cf.resolve_backend_available() is False


def test_a_bare_pytest_probes_itself_with_a_load_tolerant_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """No runner, no answer: the gate probes — and ONE retry, with a timeout that does not turn a
    busy machine into a skipped test."""
    monkeypatch.delenv("COGITATE_BACKEND_UP", raising=False)
    attempts = {"n": 0}

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def flaky(url, timeout=0):  # noqa: ANN001, ANN202
        attempts["n"] += 1
        assert timeout >= 5, "a 2s probe races a parallel start"
        if attempts["n"] == 1:
            raise OSError("connection reset by a busy box")
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", flaky)

    assert cf.resolve_backend_available() is True
    assert attempts["n"] == 2


def test_a_backend_that_is_really_down_answers_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry must not become optimism: a backend that refuses twice is down."""
    monkeypatch.delenv("COGITATE_BACKEND_UP", raising=False)

    def down(url, timeout=0):  # noqa: ANN001, ANN202
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", down)

    assert cf.resolve_backend_available() is False
