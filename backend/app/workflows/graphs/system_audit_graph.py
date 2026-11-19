"""The system-audit workflow graph (2026-08-20).

The user's framing: "tools + validation in a workflow with
secondary validation built into the workflow". The chain:

    audit → verify → analyze → report

- audit:    run the ConsistencyAudit (read-only) — the findings
- verify:   RE-RUN the audit + COMPARE (status + total_findings
            stable) — the READ-BACK, strong evidence (a log grep
            proves a request happened; a re-run proves the audit
            is reproducible). Records to the verification store.
- analyze:  summarize the findings for the report
- report:   the product lands in the display channel (the
            products page)

The verify node is the structural half of the user's ask:
UNATTENDED runs (scheduled) have nobody watching — verification
must be a NODE in the graph, not a habit.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import Paths
from app.domain.audit import ConsistencyAudit


def _paths() -> Paths:
    """THE LOCATOR for this graph, settings-derived so DATABASE_URL moves the
    database and the logs dir with it. Reading the class attributes
    (`Paths.shared_db`, `Paths.logs_dir`) would instead use the dataclass FIELD
    DEFAULTS — a fixed BASE_DIR — which is how a test run of the audit workflow
    came to read and write the operator's live installation.
    """
    from app.core.config import get_settings

    return Paths.from_settings(get_settings())

logger = logging.getLogger(__name__)


class AuditState(TypedDict, total=False):
    """Shared audit state (all keys optional; checkpoint-persisted)."""

    config: Dict[str, Any]
    inputs: Dict[str, Any]
    audit_result: Dict[str, Any]
    verify_result: Dict[str, Any]
    report_text: str
    errors: List[str]
    current_step: str


# ── the nodes ─────────────────────────────────────────────────────

def audit_node(state: AuditState) -> Dict[str, Any]:
    """Run the consistency audit + the INTEGRITY checks (read-only —
    reports the findings, never repairs)."""
    p = _paths()
    audit = ConsistencyAudit(p.shared_db)
    result = audit.run()

    # THE INTEGRITY CHECKS (2026-08-24, the sweep Phase 1): the
    # ghost-history class — dead FK targets, orphaned rows, id
    # reuse, log rotation. Rendered into the report body.
    from app.domain.audit.integrity import IntegrityAudit
    from app.core.config import Paths as _Paths
    integrity = IntegrityAudit(
        p.shared_db,
        # THE PROJECT_ROOT FIX (2026-08-25, live): the old call
        # referenced _Paths.project_root — an attribute that never
        # existed — so EVERY startup sweep died here ('Paths has no
        # attribute project_root') and nothing delivered. The
        # Paths.logs_dir is the truth.
        logs_dir=_Paths.logs_dir,
    ).render_markdown()

    return {
        "audit_result": result,
        "integrity_report": integrity,
        "current_step": "audit",
    }


def verify_node(state: AuditState) -> Dict[str, Any]:
    """The READ-BACK: re-run the audit + compare. The reproduction
    is the verification — a stable status + finding count proves
    the audit is real, not a hallucinated report."""
    audit = ConsistencyAudit(_paths().shared_db)
    rerun = audit.run()
    first = state.get("audit_result", {})
    stable = (
        first.get("status") == rerun.get("status")
        and first.get("total_findings") == rerun.get("total_findings")
    )
    verify_result = {
        "verified": stable,
        "first_status": first.get("status"),
        "rerun_status": rerun.get("status"),
        "first_findings": first.get("total_findings"),
        "rerun_findings": rerun.get("total_findings"),
        "method": "read-back (re-run + compare)",
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    # RECORD to the verification store (the honesty loop)
    try:
        from app.domain.verification import store as vstore
        vstore.record_operation(
            agent="workflow:system-audit",
            operation="system-audit",
            claimed=f"audit status={first.get('status')} findings={first.get('total_findings')}",
            verified=f"rerun status={rerun.get('status')} findings={rerun.get('total_findings')}",
            outcome="verified" if stable else "mismatched",
        )
    except Exception as e:
        logger.warning(f"verification-store record failed: {e}")
    return {
        "verify_result": verify_result,
        "current_step": "verify",
    }


def analyze_node(state: AuditState) -> Dict[str, Any]:
    """Summarize the findings into the report text."""
    result = state.get("audit_result", {})
    checks = result.get("checks", {})
    status = result.get("status", "unknown")
    total = result.get("total_findings", 0)

    lines = [
        f"# System Consistency Audit",
        f"",
        f"**Status:** {status} — {total} finding(s)",
        f"**Audited at:** {result.get('audited_at', '?')}",
        f"",
    ]
    for check_name, findings in checks.items():
        if findings:
            lines.append(f"## {check_name} — {len(findings)} finding(s)")
            for f in findings[:5]:
                label = f.get("label", check_name)
                ref = f.get("missing_agent_id") or f.get("missing_entity") or f.get("name") or "?"
                lines.append(f"- {label}: {ref} (count {f.get('count', '?')})")
            if len(findings) > 5:
                lines.append(f"- … +{len(findings) - 5} more")
            lines.append("")

    # THE INTEGRITY SECTION (the sweep Phase 1): the ghost-history
    # class findings appended to the report body.
    integrity = state.get("integrity_report", "")
    if integrity:
        lines.append("")
        lines.append(str(integrity))
        lines.append("")

    verify = state.get("verify_result", {})
    lines.append(f"## Verification")
    lines.append(f"- method: {verify.get('method', '?')}")
    lines.append(
        f"- {('VERIFIED — the re-run matches' if verify.get('verified') else 'MISMATCHED — the re-run differs')}"
    )
    lines.append(f"- first: {verify.get('first_status')}/{verify.get('first_findings')} · "
                 f"rerun: {verify.get('rerun_status')}/{verify.get('rerun_findings')}")
    lines.append("")
    # THE SCRIPTS-SWEEP POINTER (2026-08-25, the indexing fix): the
    # code-quality sweep lives separately — the next discovery lands.
    lines.append("_The code-quality sweep (path arithmetic, mypy, tests) lives in scripts/core/sweep/._")
    lines.append("")

    return {
        "report_text": "\n".join(lines),
        "current_step": "analyze",
    }


def report_node(state: AuditState) -> Dict[str, Any]:
    """Deliver the report as a workflow product (the display
    channel — the products page shows it)."""
    # the report_text IS the product; the distributor writes it to
    # the display channel on the workflow's completion (the
    # execution → product → distribution chain handles it).
    return {
        "report_text": state.get("report_text", ""),
        "current_step": "report",
    }


def create_system_audit_graph():
    """audit → verify → analyze → report."""
    builder = StateGraph(AuditState)

    builder.add_node("audit", audit_node)
    builder.add_node("verify", verify_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "audit")
    builder.add_edge("audit", "verify")
    builder.add_edge("verify", "analyze")
    builder.add_edge("analyze", "report")
    builder.add_edge("report", END)

    return builder


# ── the registration ──────────────────────────────────────────────

GRAPH_BUILDERS = {
    "system-audit": create_system_audit_graph,
}
