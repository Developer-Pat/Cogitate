"""Unit tests for AgentService.health_for_agents (F3).

Verifies health derivation from usage_logs:
- No usage → ok (healthy)
- Recent failures → warn + consecutive_failures + last_error
- 3+ consecutive failures → fail (degraded)
- Consecutive chain breaks on most-recent success
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.agents.schemas import AgentHealth
from app.domain.agents.services import AgentService
from app.infrastructure.database.models import Agent, UsageLog


async def _make_agent(db, name="Test Agent", provider="deepseek", model="deepseek-v4-flash"):
    agent = Agent(
        name=name,
        provider=provider,
        model=model,
        system_prompt="test",
        is_active=True,
        is_builtin=False,
    )
    db.add(agent)
    await db.flush()
    return agent


async def _log(db, agent_id, success, error=None, days_ago=0):
    log = UsageLog(
        session_id=1,
        agent_id=agent_id,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
        cost_usd=0.0,
        success=success,
        error_message=error,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(log)
    await db.flush()
    return log


class TestAgentHealthForAgents:
    """Health derivation from usage logs."""

    async def test_no_usage_is_ok(self, test_session):
        """Agents with no usage logs are healthy (ok)."""
        agent = await _make_agent(test_session)
        await test_session.commit()

        service = AgentService(test_session)
        health = await service.health_for_agents([agent.id])

        assert agent.id in health
        h = health[agent.id]
        assert h.status == "ok"
        assert h.consecutive_failures == 0
        assert h.last_error is None

    async def test_single_failure_warns(self, test_session):
        """One recent failure → warn with error + failure count."""
        agent = await _make_agent(test_session)
        await _log(test_session, agent.id, success=False, error="Model not found")
        await test_session.commit()

        service = AgentService(test_session)
        health = await service.health_for_agents([agent.id])

        h = health[agent.id]
        assert h.status == "warn"
        assert h.failures_7d == 1
        assert h.consecutive_failures == 1
        assert h.last_error == "Model not found"

    async def test_three_consecutive_failures_fails(self, test_session):
        """3+ consecutive failures → fail (degraded, likely broken config)."""
        agent = await _make_agent(test_session)
        await _log(test_session, agent.id, success=False, error="e1", days_ago=2)
        await _log(test_session, agent.id, success=False, error="e2", days_ago=1)
        await _log(test_session, agent.id, success=False, error="e3", days_ago=0)
        await test_session.commit()

        service = AgentService(test_session)
        health = await service.health_for_agents([agent.id])

        h = health[agent.id]
        assert h.status == "fail"
        assert h.consecutive_failures == 3
        assert h.last_error == "e3"  # most recent failure
        assert h.failures_7d == 3

    async def test_success_breaks_consecutive_chain(self, test_session):
        """A most-recent success resets the consecutive chain (warn only)."""
        agent = await _make_agent(test_session)
        await _log(test_session, agent.id, success=False, error="old fail", days_ago=2)
        await _log(test_session, agent.id, success=False, error="old fail 2", days_ago=1)
        await _log(test_session, agent.id, success=True, days_ago=0)
        await test_session.commit()

        service = AgentService(test_session)
        health = await service.health_for_agents([agent.id])

        h = health[agent.id]
        # Failures within 7d still counted → warn; chain broken → 0 consecutive
        assert h.status == "warn"
        assert h.failures_7d == 2
        assert h.consecutive_failures == 0

    async def test_empty_ids_returns_empty(self, test_session):
        """Empty agent list → empty map (no query)."""
        service = AgentService(test_session)
        health = await service.health_for_agents([])
        assert health == {}

    async def test_stale_failures_outside_window_ignored(self, test_session):
        """Failures older than 7 days must NOT count (stale warnings fix).

        Regression guard: health_for_agents previously counted ALL
        historical failures (cutoff was computed but never applied) —
        the UI showed months-old warnings as 'recent'.
        """
        agent = await _make_agent(test_session)
        # Two failures: one fresh (2d ago), one stale (30d ago)
        await _log(test_session, agent.id, success=False, error="stale failure", days_ago=30)
        await _log(test_session, agent.id, success=False, error="fresh failure", days_ago=2)
        await test_session.commit()

        service = AgentService(test_session)
        health = await service.health_for_agents([agent.id])

        h = health[agent.id]
        assert h.failures_7d == 1, "stale failure must be excluded"
        assert h.last_error == "fresh failure"
        assert h.consecutive_failures == 1
        assert h.status == "warn"

    async def test_dismissal_clears_warning(self, test_session):
        """Dismissing acknowledges failures up to that moment (F6).

        After dismiss_health, failures BEFORE the dismissal must not
        flag the agent → status ok.
        """
        agent = await _make_agent(test_session)
        await _log(test_session, agent.id, success=False, error="old failure", days_ago=2)
        await test_session.commit()

        service = AgentService(test_session)
        # Before dismiss: warn
        health = await service.health_for_agents([agent.id])
        assert health[agent.id].status == "warn"

        # Dismiss → failures acknowledged → ok
        assert await service.dismiss_health(agent.id) is True
        health = await service.health_for_agents([agent.id])
        assert health[agent.id].status == "ok"
        assert health[agent.id].failures_7d == 0

    async def test_new_failure_after_dismissal_reflags(self, test_session):
        """A failure AFTER dismissal re-flags the agent (F6).

        Dismissal is not permanent — it acknowledges the past, not the
        future. The next failure brings the warning back.
        """
        agent = await _make_agent(test_session)
        await _log(test_session, agent.id, success=False, error="old", days_ago=3)
        await test_session.commit()

        service = AgentService(test_session)
        await service.dismiss_health(agent.id)
        health = await service.health_for_agents([agent.id])
        assert health[agent.id].status == "ok"

        # New failure after dismissal
        await _log(test_session, agent.id, success=False, error="new failure", days_ago=0)
        await test_session.commit()

        health = await service.health_for_agents([agent.id])
        h = health[agent.id]
        assert h.status == "warn"
        assert h.last_error == "new failure"
        assert h.failures_7d == 1

    async def test_undismiss_restores_warning(self, test_session):
        """Undismissing removes the acknowledgment — warning returns (F6)."""
        agent = await _make_agent(test_session)
        await _log(test_session, agent.id, success=False, error="still relevant", days_ago=1)
        await test_session.commit()

        service = AgentService(test_session)
        await service.dismiss_health(agent.id)
        assert (await service.health_for_agents([agent.id]))[agent.id].status == "ok"

        assert await service.undismiss_health(agent.id) is True
        health = await service.health_for_agents([agent.id])
        assert health[agent.id].status == "warn"
