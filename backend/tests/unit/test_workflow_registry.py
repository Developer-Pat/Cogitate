"""Workflow product addressing — a named recipient's inbox, failing loudly on an unknown name.

- AgentDistributor: a workflow product is handed to a NAMED agent
  (file-it: the agent's inbox; hand-it-a-task: a chat message).
  The name resolves STRICT via the registry — an unknown recipient
  fails loudly (dead-letter, not a hang).
- The agent node accepts agent_name in the config and resolves it
  via resolve_agent before invoking.
"""

import sys
sys.path.insert(0, "backend")

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.collections import models as _cm  # noqa: F401
from app.domain.tools import team_tools  # noqa: F401


class TestAgentDistributor:
    def _product(self, recipient: str, mode: str = "file-it"):
        from app.workflows.distribution.models import WorkflowProduct
        return WorkflowProduct(
            product_type="test_product", title="T", body="b",
            source_template="t", created_at="2026-08-16T00:00:00Z",
            meta={"recipient_agent": recipient, "recipient_mode": mode},
        )

    def _deliver_in_thread(self, distributor, product):
        """deliver is sync + uses asyncio.run — run it in a thread
        so the pytest event loop isn't nested."""
        import threading
        result = {}
        def _run():
            result["r"] = distributor.deliver(product)
        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=15)
        return result.get("r")

    def _distributor(self, tmp_path: Path, session_factory):
        from app.workflows.distribution.distributors import AgentDistributor
        return AgentDistributor(
            agents_root=tmp_path, session_factory=session_factory,
        )

    def _test_session_factory(self, engine):
        """A sessionmaker bound to the conftest's test engine — so
        the distributor's thread sees what the test committed."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def test_file_it_writes_to_agent_inbox(self, test_session: AsyncSession, test_engine, tmp_path: Path):
        """The product lands in the addressed agent's inbox folder."""
        from app.domain.agents.services import AgentService
        from app.domain.agents.schemas import AgentCreate
        from app.workflows.distribution.distributors import AgentDistributor

        svc = AgentService(test_session)
        await svc.create(AgentCreate(
            name="Dist Recipient", description="d", provider="deepseek",
            model="deepseek-v4-flash",
        ))
        await test_session.commit()
        d = self._distributor(tmp_path, self._test_session_factory(test_engine))
        result = self._deliver_in_thread(d, self._product("Dist Recipient"))
        assert result is not None and result.success
        inbox = tmp_path / "Dist Recipient" / "inbox"
        assert inbox.exists()
        assert any(inbox.iterdir())

    async def test_unknown_recipient_fails_loudly(self, test_session: AsyncSession, test_engine, tmp_path: Path):
        """The registry is STRICT — an unknown name is a dead-letter."""
        d = self._distributor(tmp_path, self._test_session_factory(test_engine))
        result = self._deliver_in_thread(d, self._product("No Such Agent"))
        assert result is not None and not result.success
        assert "No agent named" in result.detail

    async def test_no_recipient_rejected(self, test_session: AsyncSession, tmp_path: Path):
        from app.workflows.distribution.models import WorkflowProduct
        from app.workflows.distribution.distributors import AgentDistributor
        d = AgentDistributor(agents_root=tmp_path)
        prod = WorkflowProduct(
            product_type="t", title="T", body="b", source_template="t",
            created_at="2026-08-16T00:00:00Z", meta={},
        )
        result = d.deliver(prod)
        assert not result.success
        assert "recipient_agent" in result.detail
