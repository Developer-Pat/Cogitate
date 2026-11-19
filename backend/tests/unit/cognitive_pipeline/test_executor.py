"""The agent executor — running a step, and the executor registry."""

import pytest
from app.domain.providers.capabilities import SOURCE_AGENT, ServiceCandidate
from app.services.cognitive_pipeline.executor import (
    ExecutorRegistry,
    DefaultExecutor,
    LiteLLMExecutor,
    create_default_registry,
    run_executor,
)
from app.services.cognitive_pipeline.models import (
    AgentDescriptor,
    Context,
)


class TestDefaultExecutor:
    @pytest.mark.asyncio
    async def test_execute_returns_response(self):
        executor = DefaultExecutor()
        agent = AgentDescriptor(
            id=1,
            name="TestBot",
            description="A test agent",
            provider="ollama",
            model="llama3.2",
        )
        context = Context(
            user_message="Tell me about Python",
            system_prompt="You are a Python expert.",
            agent_name="TestBot",
        )
        response = await executor.execute(context=context, agent=agent)
        assert "TestBot" in response
        assert "Tell me about Python" in response
        assert "A test agent" in response
        assert "ollama" in response

    @pytest.mark.asyncio
    async def test_execute_with_history(self):
        executor = DefaultExecutor()
        agent = AgentDescriptor(id=1, name="Historian")
        context = Context(
            user_message="What happened in 1066?",
            session_history=[{"role": "user", "content": "Hi"}],
            agent_name="Historian",
        )
        response = await executor.execute(context=context, agent=agent)
        assert "Historian" in response
        assert "1066" in response


class TestExecutorRegistry:
    def test_default_registry_has_default(self):
        registry = create_default_registry()
        assert "default" in registry
        assert registry.list() == ["default", "fast", "hybrid", "stub"]

    def test_register_custom_executor(self):
        registry = ExecutorRegistry()
        executor = DefaultExecutor()
        registry.register("custom", executor)
        assert registry.get("custom") is executor

    def test_get_missing_raises_key_error(self):
        registry = ExecutorRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")


class TestRunExecutor:
    @pytest.mark.asyncio
    async def test_run_with_tracing(self):
        executor = DefaultExecutor()
        agent = AgentDescriptor(id=1, name="TestBot")
        context = Context(
            user_message="Hello",
            agent_name="TestBot",
        )
        response, trace = await run_executor(
            executor=executor,
            context=context,
            agent=agent,
        )
        assert response
        assert trace.strategy == "default"
        assert trace.duration_ms >= 0
        assert trace.tokens_used > 0

    @pytest.mark.asyncio
    async def test_run_propagates_exception(self):
        class FailingExecutor(DefaultExecutor):
            async def execute(self, **kwargs):
                msg = "Executor failure"
                raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="Executor failure"):
            await run_executor(
                executor=FailingExecutor(),
                context=Context(user_message="Hi", agent_name="Test"),
                agent=AgentDescriptor(id=1, name="Test"),
            )


class TestLiteLLMExecutorFallback:
    """F4 — provider failover honoring agent fallback config."""

    @pytest.fixture(autouse=True)
    def _mock_litellm(self, monkeypatch):
        """Mock litellm.acompletion with a configurable sequence."""
        self.calls = []

        async def fake_acompletion(model, messages, **kwargs):
            self.calls.append(model)
            failure = self.failures.pop(0) if self.failures else None
            if failure is not None:
                raise failure
            class Msg:
                content = "ok from " + model
            class Choice:
                message = Msg()
            class Resp:
                choices = [Choice()]
            return Resp()

        self.failures: list[Exception] = []
        # The executor imports acompletion locally inside _call_with_fallback
        # (`from litellm import acompletion`), so patch the litellm module —
        # the local import resolves to our fake on every call.
        monkeypatch.setattr(
            "litellm.acompletion", fake_acompletion,
        )

    def _chain(self, *specs):
        """The RESOLVER's answer, as the chat paths thread it onto the descriptor (R3)."""
        return tuple(
            ServiceCandidate(ordinal=index, provider=provider, model=model, source=SOURCE_AGENT)
            for index, (provider, model) in enumerate(specs)
        )

    def _agent(self, fallback=False, chain=None):
        """A descriptor carrying a chain only when a resolution supplied one."""
        return AgentDescriptor(
            id=1, name="F4Bot", provider="deepseek", model="deepseek-v4-flash",
            fallback_enabled=fallback, candidates=chain or (),
        )

    def _context(self):
        return Context(user_message="hello", agent_name="F4Bot")

    @pytest.mark.asyncio
    async def test_primary_success_no_failover(self):
        """Primary works → one call, and the chain's backups are never touched."""
        executor = LiteLLMExecutor()
        response = await executor.execute(
            context=self._context(),
            agent=self._agent(
                fallback=True,
                chain=self._chain(
                    ("deepseek", "deepseek-v4-flash"), ("ollama", "deepseek-v4-flash")
                ),
            ),
        )
        assert response == "ok from deepseek/deepseek-v4-flash"
        assert self.calls == ["deepseek/deepseek-v4-flash"]

    @pytest.mark.asyncio
    async def test_fallback_disabled_raises(self):
        """fallback_enabled=False → the primary's failure raises, the backups untouched."""
        executor = LiteLLMExecutor()
        self.failures = [RuntimeError("provider down")]
        with pytest.raises(RuntimeError, match="provider down"):
            await executor.execute(
                context=self._context(),
                agent=self._agent(
                    fallback=False,
                    chain=self._chain(
                        ("deepseek", "deepseek-v4-flash"), ("ollama", "deepseek-v4-flash")
                    ),
                ),
            )
        assert self.calls == ["deepseek/deepseek-v4-flash"]

    @pytest.mark.asyncio
    async def test_fallback_enabled_walks_the_resolved_chain(self):
        """fallback_enabled=True → the RESOLUTION's order is walked once the primary fails."""
        executor = LiteLLMExecutor()
        self.failures = [RuntimeError("primary down")]
        agent = self._agent(
            fallback=True,
            chain=self._chain(
                ("deepseek", "deepseek-v4-flash"),
                ("ollama", "deepseek-v4-flash"),
                ("openrouter", "deepseek-v4-flash"),
            ),
        )
        response = await executor.execute(context=self._context(), agent=agent)
        # `ollama` rides litellm's TOOL-CAPABLE handler now, the same one the chat path uses
        # (`litellm_route`) — this executor used to send the raw `ollama/` prefix, which is the
        # function-unsupported handler, so the two paths disagreed about the protocol.
        assert response == "ok from ollama_chat/deepseek-v4-flash"
        assert self.calls == [
            "deepseek/deepseek-v4-flash",
            "ollama_chat/deepseek-v4-flash",
        ]

    @pytest.mark.asyncio
    async def test_no_resolution_means_one_attempt_and_no_hardcoded_chain(self):
        """No chain on the descriptor → the executor's own single attempt, and nothing invented.

        This is what replaced `DEFAULT_FALLBACK_CHAIN`: the executor has no chain of its own any
        more, so an agent with the flag on and no resolver reading fails visibly instead of walking
        three hardcoded providers.
        """
        from app.services.cognitive_pipeline import executor as executor_module

        assert not hasattr(executor_module, "DEFAULT_FALLBACK_CHAIN")

        executor = LiteLLMExecutor()
        self.failures = [RuntimeError("primary down")]
        with pytest.raises(RuntimeError, match="primary down"):
            await executor.execute(
                context=self._context(), agent=self._agent(fallback=True)
            )
        assert self.calls == ["deepseek/deepseek-v4-flash"]

    @pytest.mark.asyncio
    async def test_all_fallbacks_fail_raises_last(self):
        """Every candidate fails → the LAST error propagates (no silent empty)."""
        executor = LiteLLMExecutor()
        self.failures = [
            RuntimeError("p down"), RuntimeError("o down"),
            RuntimeError("oll down"),
        ]
        agent = self._agent(
            fallback=True,
            chain=self._chain(
                ("deepseek", "deepseek-v4-flash"),
                ("openrouter", "deepseek-v4-flash"),
                ("ollama", "deepseek-v4-flash"),
            ),
        )
        with pytest.raises(RuntimeError, match="oll down"):
            await executor.execute(context=self._context(), agent=agent)
        # the chain's three candidates, attempted in order
        assert len(self.calls) == 3

    @pytest.mark.asyncio
    async def test_a_degraded_turn_reports_the_chain_in_its_trace(self):
        """The response's TRACE names what was tried — a degraded turn is not only in the log."""
        executor = LiteLLMExecutor()
        self.failures = [RuntimeError("primary down")]
        agent = self._agent(
            fallback=True,
            chain=self._chain(("deepseek", "deepseek-v4-flash"), ("ollama", "deepseek-v4-flash")),
        )

        response, trace = await run_executor(
            executor=executor, context=self._context(), agent=agent
        )

        # The trace names WHO was tried — the candidates' `provider/model`, not the litellm string
        # (`capabilities.attempt_chain` records `candidate.describe()`), so the remap does not show here.
        assert response == "ok from ollama_chat/deepseek-v4-flash"
        assert trace.metadata["fallback_chain_used"] == ["ollama/deepseek-v4-flash"]
