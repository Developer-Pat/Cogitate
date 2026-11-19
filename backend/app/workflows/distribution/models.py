"""
Workflow Product Distribution — models.

A workflow PRODUCES a product (digest, alert, report). The
distribution layer packages it into a WorkflowProduct (the
aggregator's job, thin here because execution records already
carry the output) and delivers it through distributors (file,
display, later email/sms/toast).

Phase A (2026-08-10): the aggregator role is folded into the
product contract — the deliver nodes build a WorkflowProduct from
workflow state. A full Aggregator ABC is deferred until a second
aggregation source exists (roadmap decision A4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WorkflowProduct:
    """The packaged output of a workflow run.

    Attributes:
        product_type: stable slug, e.g. "rss_digest", "market_alert",
            "readiness_report" (drives file naming + display badges)
        title: human title, e.g. "RSS Digest — 2026-08-10"
        body: the product content (markdown)
        source_template: template_id that produced it
        created_at: ISO timestamp (Z suffix)
        path: delivered file path (set by FileDistributor)
        meta: free-form extras (item counts, errors, thresholds…)
    """

    product_type: str
    title: str
    body: str
    source_template: str
    created_at: str
    path: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """Outcome of one distributor delivering one product."""

    distributor: str
    success: bool
    detail: str = ""
    path: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "distributor": self.distributor,
            "success": self.success,
            "detail": self.detail,
            "path": self.path,
        }
