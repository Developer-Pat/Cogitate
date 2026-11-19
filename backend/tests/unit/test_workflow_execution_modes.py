"""The workflow trace level — debug by default, releasable on request.

trace_level gates CAPTURE only — the graph and its behavior are
identical. Debug streams per-node snapshots; release is lean.
"""

import sys
sys.path.insert(0, "backend")

from sqlalchemy import select

from app.domain.providers.capabilities import WORKFLOW_CAPABILITY_KEY
from app.infrastructure.database.models import Capability, CapabilityService, Provider
from app.workflows.api.workflow_router import ExecuteWorkflowRequest, _build_initial_state


class TestExecuteWorkflowRequest:
    def test_trace_level_defaults_to_debug(self):
        req = ExecuteWorkflowRequest(
            template_id="readiness-check",
            initial_message="run",
        )
        assert req.trace_level == "debug"

    def test_trace_level_accepts_release(self):
        req = ExecuteWorkflowRequest(
            template_id="readiness-check",
            initial_message="run",
            trace_level="release",
        )
        assert req.trace_level == "release"

    def test_trace_level_accepts_explicit_debug(self):
        req = ExecuteWorkflowRequest(
            template_id="readiness-check",
            initial_message="run",
            trace_level="debug",
        )
        assert req.trace_level == "debug"


class TestRunMetadata:
    def test_metadata_carries_trace_fields(self):
        from app.workflows.state.workflow_state import RunMetadata
        md = RunMetadata(
            workflow_id="wf-x",
            template_id="tpl-x",
            status="completed",
            trace_level="debug",
            node_snapshots=[{"node": "readiness_probe", "state": {}}],
        )
        assert md.trace_level == "debug"
        assert len(md.node_snapshots) == 1

    def test_the_error_path_copies_a_resolution_and_the_run_config(self):
        """A failed run must not lose what it carried — the old rebuild dropped it."""
        from app.workflows.api.workflow_router import _error_metadata
        from app.workflows.state.workflow_state import LLMResolution, RunMetadata

        carried = RunMetadata(
            workflow_id="wf-1",
            template_id="tpl-1",
            config={"feeds": ["a"]},
            tags=["monitor"],
            trace_level="debug",
            llm_resolution=LLMResolution(
                provider="llama", model="Bonsai-27B-Q1_0.gguf", rung="capability config"
            ),
        )
        md = _error_metadata({"metadata": carried}, "wf-1", "boom", retry_attempts=3)

        assert (md.status, md.error, md.retry_attempts) == ("error", "boom", 3)
        # the fields a REBUILD silently dropped (config/tags/trace_level/llm_resolution)
        assert md.config == {"feeds": ["a"]}
        assert md.tags == ["monitor"]
        assert md.trace_level == "debug"
        assert md.llm_resolution is not None
        assert (
            md.llm_resolution.provider,
            md.llm_resolution.model,
            md.llm_resolution.rung,
        ) == ("llama", "Bonsai-27B-Q1_0.gguf", "capability config")
        # a COPY, not a mutation of the run's carried object
        assert carried.status == "running"

    def test_the_error_path_carries_the_statement_and_keeps_the_raw_error(self):
        """Stage 3: the run-level panel reads the ONE wording; the raw exception stays in `error`."""
        from app.workflows.api.workflow_router import _error_metadata
        from app.workflows.state.workflow_state import LLMResolution, RunMetadata

        carried = RunMetadata(
            workflow_id="wf-1",
            template_id="tpl-1",
            llm_resolution=LLMResolution(
                provider="llama", model="m", rung="capability config"
            ),
        )
        md = _error_metadata(
            {"metadata": carried},
            "wf-1",
            "boom",
            failure_statement="Llama (llama) is not functioning properly — boom.",
        )

        assert md.failure_statement == "Llama (llama) is not functioning properly — boom."
        assert md.error == "boom"  # the RAW exception is still recoverable
        assert carried.failure_statement is None  # a COPY, not a mutation of the run's object

    def test_no_statement_leaves_the_field_none(self):
        """A run that named nobody (G4-F5) carries no statement — the panel shows the raw error."""
        from app.workflows.api.workflow_router import _error_metadata

        md = _error_metadata({"template_id": "tpl-2"}, "wf-2", "boom")

        assert md.failure_statement is None
        assert md.error == "boom"

    def test_the_error_path_with_no_carried_metadata_builds_the_minimum(self):
        from app.workflows.api.workflow_router import _error_metadata

        md = _error_metadata({"template_id": "tpl-2"}, "wf-2", "boom")

        assert (md.status, md.template_id, md.llm_resolution) == ("error", "tpl-2", None)


async def _own_workflow_llm(test_session) -> Capability:
    """Provision a `workflow-llm` capability pointing at a provider row of our own.

    The copied installation SEEDS a `workflow-llm` row, and `auto_clean_tables` truncates
    `capabilities` between tests — so the row may or may not be there. Own it either way.
    """
    existing = (
        await test_session.execute(
            select(Capability).where(Capability.key == WORKFLOW_CAPABILITY_KEY)
        )
    ).scalar_one_or_none()
    if existing is not None:
        await test_session.delete(existing)
        await test_session.flush()

    provider = Provider(
        name="zz-run-llm",
        display_name="Run LLM",
        provider_type="deepseek",
        base_url="https://api.deepseek.com/v1",
        is_active=True,
        config={"default_model": "deepseek-v4-flash"},
    )
    test_session.add(provider)
    await test_session.flush()

    capability = Capability(
        key=WORKFLOW_CAPABILITY_KEY, label="Workflow LLM", kind="llm", enabled=True
    )
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(
            capability_id=capability.id, ordinal=0, provider_id=provider.id, enabled=True
        )
    )
    await test_session.commit()
    return capability


class TestRunCarriesItsResolution:
    """G4-F2 — the run resolves its LLM at its start and carries it as data."""

    async def test_the_run_carries_the_service_it_resolved(self, test_session):
        await _own_workflow_llm(test_session)
        req = ExecuteWorkflowRequest(template_id="tpl", initial_message="go")

        state = await _build_initial_state(test_session, req, "wf-1", {}, [])

        res = state["metadata"].llm_resolution
        assert res is not None
        assert (res.provider, res.model, res.rung) == (
            "zz-run-llm", "deepseek-v4-flash", "capability config",
        )
        assert state["metadata"].status == "running"

    async def test_a_disabled_capability_carries_its_rung_and_names_nobody(self, test_session):
        capability = await _own_workflow_llm(test_session)
        capability.enabled = False
        await test_session.commit()
        req = ExecuteWorkflowRequest(template_id="tpl", initial_message="go")

        state = await _build_initial_state(test_session, req, "wf-1", {}, [])

        res = state["metadata"].llm_resolution
        assert res is not None
        assert (res.provider, res.model, res.rung) == (None, None, "disabled")

    async def test_a_failed_read_carries_none_and_the_run_still_starts(
        self, test_session, monkeypatch
    ):
        async def boom(*_a, **_k):
            raise RuntimeError("db gone")

        monkeypatch.setattr("app.domain.providers.capabilities.resolve", boom)
        req = ExecuteWorkflowRequest(template_id="tpl", initial_message="go")

        state = await _build_initial_state(test_session, req, "wf-1", {}, [])

        assert state["metadata"].llm_resolution is None
        assert state["metadata"].status == "running"


class _ProviderError(Exception):
    """The slice of a PROVIDER-LAYER error `is_provider_failure` reads.

    litellm sets `llm_provider` on every error it raises (measured), and its classes live in
    `litellm.exceptions` — either signal is enough. A stand-in keeps the tests off the library.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.llm_provider = "deepseek"


class TestIsProviderFailure:
    """The G4-F5 signal itself — WHO the exception belongs to, decided against the real library."""

    def test_a_real_litellm_error_is_recognised(self):
        from litellm import exceptions as litellm_exceptions

        from app.domain.providers.failure_statement import is_provider_failure

        error = litellm_exceptions.APIConnectionError(
            "boom", llm_provider="ollama", model="phi4-mini:latest"
        )

        assert is_provider_failure(error) is True

    def test_an_app_error_is_not_a_provider_failure(self):
        from app.domain.providers.failure_statement import is_provider_failure

        assert is_provider_failure(RuntimeError('No synchronous function provided to "probe"')) is False
        assert is_provider_failure(RuntimeError("Cannot operate on a closed database.")) is False
        assert is_provider_failure(KeyError("no such node")) is False

    def test_the_litellm_attribute_is_the_second_signal(self):
        from app.domain.providers.failure_statement import is_provider_failure

        class _WrappedError(Exception):
            llm_provider: str

        error = _WrappedError("boom")
        assert is_provider_failure(error) is False
        error.llm_provider = "deepseek"
        assert is_provider_failure(error) is True


class TestTheWorkflowStatement:
    """G4-F3 and the G4-F5 gate: the workflow path names the offender ONLY when the failure is the
    provider layer's. A run carries a resolution either way, so a false name is the easy mistake."""

    def test_the_statement_names_the_resolution_when_the_provider_failed(self):
        from app.workflows.utils.run_failure import run_failure_statement
        from app.workflows.state.workflow_state import LLMResolution, RunMetadata

        md = RunMetadata(
            workflow_id="wf-1",
            template_id="tpl-1",
            llm_resolution=LLMResolution(
                provider="deepseek", model="deepseek-v4-flash", rung="capability config"
            ),
        )
        statement = run_failure_statement(md, _ProviderError("boom"))

        assert statement == (
            "Deepseek V4 Flash (deepseek) is not functioning properly — "
            "the provider reported: boom. You can have Exa attempt diagnosis (ask Exa)."
        )

    def test_a_non_llm_failure_names_nobody_even_with_a_resolution(self):
        """THE CORRECTION: the failures that actually reach this branch are infrastructure — a
        node's TypeError, a closed database — and naming the service the run resolved for them
        would finger an innocent provider. Falling back to the raw error is the honest answer."""
        from app.workflows.utils.run_failure import run_failure_statement
        from app.workflows.state.workflow_state import LLMResolution, RunMetadata

        md = RunMetadata(
            workflow_id="wf-1",
            template_id="tpl-1",
            llm_resolution=LLMResolution(
                provider="deepseek", model="deepseek-v4-flash", rung="capability config"
            ),
        )

        assert run_failure_statement(md, RuntimeError("boom")) is None
        assert (
            run_failure_statement(md, RuntimeError('No synchronous function provided to "probe"'))
            is None
        )
        assert run_failure_statement(md, RuntimeError("Cannot operate on a closed database.")) is None

    def test_a_run_that_resolved_nobody_names_nobody(self):
        """A non-LLM failure has no offender to finger (G4-F5), and a run that carried no
        resolution at all falls back to the raw error."""
        from app.workflows.utils.run_failure import run_failure_statement
        from app.workflows.state.workflow_state import LLMResolution, RunMetadata

        no_resolution = RunMetadata(workflow_id="w", template_id="t")
        assert run_failure_statement(no_resolution, RuntimeError("boom")) is None

        resolved_to_nothing = RunMetadata(
            workflow_id="w", template_id="t", llm_resolution=LLMResolution(rung="disabled")
        )
        assert run_failure_statement(resolved_to_nothing, RuntimeError("boom")) is None


class TestTheStatusReader:
    """`/status` reads three metadata shapes through ONE reader — the panel's statement included.

    The three shapes are real: a `RunMetadata` object, a plain dict, and a corrupted repr string
    from an older checkpoint. Before Stage 3 the same three-way branch lived inline in the
    endpoint, so a new field could be added to two branches and silently missed in the third.
    """

    def test_it_reads_a_metadata_object(self):
        from app.workflows.api.workflow_router import _read_run_status_metadata
        from app.workflows.state.workflow_state import RunMetadata

        md = RunMetadata(
            workflow_id="w",
            template_id="t",
            status="error",
            error="raw boom",
            failure_statement="The statement.",
        )
        fields = _read_run_status_metadata(md)

        assert (fields["status"], fields["error"]) == ("error", "raw boom")
        assert fields["failure_statement"] == "The statement."

    def test_it_reads_a_plain_dict(self):
        from app.workflows.api.workflow_router import _read_run_status_metadata

        fields = _read_run_status_metadata(
            {"status": "error", "error": "raw boom", "failure_statement": "The statement."}
        )

        assert (
            fields["status"],
            fields["error"],
            fields["failure_statement"],
        ) == ("error", "raw boom", "The statement.")

    def test_it_reads_a_corrupted_repr_string(self):
        from app.workflows.api.workflow_router import _read_run_status_metadata

        text = (
            "RunMetadata(workflow_id='w', template_id='t', status='error', error='raw boom', "
            "retry_attempts=3, failure_statement='The statement.')"
        )
        fields = _read_run_status_metadata(text)

        assert (fields["status"], fields["error"]) == ("error", "raw boom")
        assert fields["failure_statement"] == "The statement."

    def test_a_literal_none_statement_reads_as_absent(self):
        """The repr branch must not turn `failure_statement='None'` into a bogus panel line."""
        from app.workflows.api.workflow_router import _read_run_status_metadata

        fields = _read_run_status_metadata(
            "RunMetadata(workflow_id='w', status='error', failure_statement='None')"
        )

        assert fields["failure_statement"] is None


class TestTheRunFailureToast:
    """Stage 3 — a failed run that NAMED somebody toasts; one that named nobody stays silent."""

    def test_the_toast_fires_with_the_one_wording(self, monkeypatch):
        from app.workflows.api.workflow_router import _announce_run_failure

        published: list[tuple] = []
        monkeypatch.setattr(
            "app.domain.messaging.services.publish_warning",
            lambda title, message, kind="provider-fallback": published.append(
                (title, message, kind)
            ),
        )

        _announce_run_failure("wf-1", "Deepseek (deepseek) is not functioning properly — boom.")

        assert published == [
            (
                "Workflow run failed",
                "Deepseek (deepseek) is not functioning properly — boom.",
                "workflow-failure",
            )
        ]

    def test_a_run_that_named_nobody_does_not_toast(self, monkeypatch):
        """G4-F5: a non-LLM failure has no offender to announce — the panel carries its raw error."""
        from app.workflows.api.workflow_router import _announce_run_failure

        published: list[tuple] = []
        monkeypatch.setattr(
            "app.domain.messaging.services.publish_warning",
            lambda *a, **k: published.append(a),
        )

        _announce_run_failure("wf-1", None)

        assert published == []

    async def test_the_failed_branch_toasts_and_carries_the_statement(self, monkeypatch):
        """THE WIRING: a real failed run publishes the toast AND puts the statement on its metadata.

        This drives `run_workflow_async`'s failed branch — the retry loop is replaced (no sleeps)
        and the DB/bus writes are stubbed — so the assertion is about the CALL SITE, not only the
        helper. Reverting the call in the branch turns this red while the two helper tests stay green.
        """
        from types import SimpleNamespace

        import importlib

        from app.workflows.error_handling.retry import RetryResult
        from app.workflows.state.workflow_state import LLMResolution, RunMetadata

        wr = importlib.import_module("app.workflows.api.workflow_router")

        published: list[tuple] = []
        monkeypatch.setattr(
            "app.domain.messaging.services.publish_warning",
            lambda title, message, kind="provider-fallback": published.append(
                (title, message, kind)
            ),
        )
        monkeypatch.setattr("app.domain.messaging.services.publish", lambda *a, **k: None)
        monkeypatch.setattr(wr, "record_execution_complete", lambda *a, **k: None)
        monkeypatch.setattr(
            wr,
            "LangfuseManager",
            SimpleNamespace(
                run_trace_id=lambda workflow_id: "0" * 32,
                with_run_metadata=lambda config, **kw: config,
                get_langfuse_handler=lambda **k: None,
                flush=lambda: None,
            ),
        )
        monkeypatch.setattr(
            wr,
            "execute_with_retry",
            lambda func, **k: RetryResult(success=False, error=_ProviderError("boom"), attempts=1),
        )

        class _GraphStub:
            def __init__(self) -> None:
                self.updated: dict = {}

            def update_state(self, config, state):
                self.updated = state

        graph = _GraphStub()
        initial_state = {
            "template_id": "tpl",
            "metadata": RunMetadata(
                workflow_id="wf-1",
                template_id="tpl",
                llm_resolution=LLMResolution(
                    provider="deepseek", model="deepseek-v4-flash", rung="capability config"
                ),
            ),
        }

        await wr.run_workflow_async(graph, initial_state, {}, "wf-1", "debug")

        assert len(published) == 1, "a failed run that named its service must reach the toast"
        title, message, kind = published[0]
        assert (title, kind) == ("Workflow run failed", "workflow-failure")
        # the SAME sentence the panel reads, carried on the run's error metadata
        assert graph.updated["metadata"].failure_statement == message
        assert graph.updated["metadata"].error == "boom"  # the raw exception stays recoverable
