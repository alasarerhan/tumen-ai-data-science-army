from __future__ import annotations

"""c5_reports.

Deterministic report-template tools supporting **C5 — Rapor
genişletmesi** (spec ``docs/specs/C5-report-templates.md``).

The actual PDF/PPTX rendering is a UI/convert concern (out of
scope for this tool).  This module provides the deterministic
core: template registry, schedule computation, and a Markdown
renderer that downstream workers can feed to a PDF/PPTX
converter.

Public surface
--------------

* :func:`TEMPLATES` — built-in template registry.
* :func:`get_template(template_id)` — look up a template by id.
* :func:`build_report` — build a report for a given template,
  period, and KPI/event payload.
* :func:`render_markdown` — render a built report to Markdown.
* :func:`compute_schedule` — period-aware next-run timestamp.
"""

import uuid  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Optional, Sequence  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------


TEMPLATES: Dict[str, Dict[str, Any]] = {
    "weekly_kpi_summary": {
        "title": "Weekly KPI Summary",
        "format": ["markdown", "pdf", "pptx"],
        "sections": [
            "header",
            "kpis",
            "anomalies",
            "trends",
        ],
        "schedule_hint": "weekly",
    },
    "experiment_results": {
        "title": "Experiment Results",
        "format": ["markdown", "pdf"],
        "sections": [
            "header",
            "design_summary",
            "metrics",
            "decision",
            "next_steps",
        ],
        "schedule_hint": "oneoff",
    },
    "model_drift_alert": {
        "title": "Model Drift Alert",
        "format": ["markdown"],
        "sections": [
            "header",
            "drift_signals",
            "retrain_recommendation",
        ],
        "schedule_hint": "event",
    },
    "fairness_audit_summary": {
        "title": "Fairness & Bias Audit",
        "format": ["markdown", "pdf"],
        "sections": [
            "header",
            "protected_attribute_metrics",
            "recommendations",
        ],
        "schedule_hint": "monthly",
    },
}


def get_template(template_id: str) -> Dict[str, Any]:
    """Return the template dict for ``template_id``."""
    if template_id not in TEMPLATES:
        raise KeyError(f"Unknown template id: {template_id!r}")
    return TEMPLATES[template_id]


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def build_report(
    template_id: str,
    *,
    period_start: str = "2026-07-01",
    period_end: str = "2026-07-07",
    kpis: Optional[Sequence[Mapping[str, Any]]] = None,
    anomalies: Optional[Sequence[str]] = None,
    design_summary: Optional[str] = None,
    metrics: Optional[Sequence[Mapping[str, Any]]] = None,
    decision: Optional[str] = None,
    next_steps: Optional[Sequence[str]] = None,
    drift_signals: Optional[Sequence[Mapping[str, Any]]] = None,
    retrain_recommendation: Optional[str] = None,
    protected_attribute_metrics: Optional[Sequence[Mapping[str, Any]]] = None,
    recommendations: Optional[Sequence[str]] = None,
    title: Optional[str] = None,
    report_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a report dict for the given template id.

    Sections not relevant to the template are ignored; missing
    sections are simply absent from the resulting dict.
    """
    tpl = get_template(template_id)
    if report_id is None:
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
    body: Dict[str, Any] = {
        "report_id": report_id,
        "template_id": template_id,
        "title": title or tpl["title"],
        "format": list(tpl["format"]),
        "schedule_hint": tpl["schedule_hint"],
        "created_at": created_at,
        "period_start": period_start,
        "period_end": period_end,
    }
    if "header" in tpl["sections"]:
        body["header"] = {
            "title": body["title"],
            "period_start": period_start,
            "period_end": period_end,
        }
    if "kpis" in tpl["sections"] and kpis is not None:
        body["kpis"] = list(kpis)
    if "anomalies" in tpl["sections"] and anomalies is not None:
        body["anomalies"] = list(anomalies)
    if "trends" in tpl["sections"] and kpis is not None:
        # Derive trend direction from delta sign.
        body["trends"] = [
            {
                "name": k.get("name"),
                "direction": "up"
                if (k.get("delta") or 0) > 0
                else "down" if (k.get("delta") or 0) < 0 else "flat",
            }
            for k in kpis
        ]
    if "design_summary" in tpl["sections"] and design_summary is not None:
        body["design_summary"] = design_summary
    if "metrics" in tpl["sections"] and metrics is not None:
        body["metrics"] = list(metrics)
    if "decision" in tpl["sections"] and decision is not None:
        body["decision"] = decision
    if "next_steps" in tpl["sections"] and next_steps is not None:
        body["next_steps"] = list(next_steps)
    if "drift_signals" in tpl["sections"] and drift_signals is not None:
        body["drift_signals"] = list(drift_signals)
    if "retrain_recommendation" in tpl["sections"] and retrain_recommendation is not None:
        body["retrain_recommendation"] = retrain_recommendation
    if "protected_attribute_metrics" in tpl["sections"] and protected_attribute_metrics is not None:
        body["protected_attribute_metrics"] = list(protected_attribute_metrics)
    if "recommendations" in tpl["sections"] and recommendations is not None:
        body["recommendations"] = list(recommendations)
    return body


# ---------------------------------------------------------------------------
# Schedule computation
# ---------------------------------------------------------------------------


_PERIOD_SECONDS = {
    "daily": 86_400,
    "weekly": 86_400 * 7,
    "monthly": 86_400 * 30,
    "quarterly": 86_400 * 90,
}


def compute_schedule(
    period: str,
    starting_at_epoch: float,
    n_runs: int = 1,
) -> List[float]:
    """Return the next ``n_runs`` schedule timestamps (epoch seconds)."""
    if period not in _PERIOD_SECONDS and period != "oneoff" and period != "event":
        raise ValueError(f"Unsupported period: {period!r}")
    if period == "oneoff" or period == "event":
        return [starting_at_epoch] * n_runs
    step = _PERIOD_SECONDS[period]
    return [starting_at_epoch + i * step for i in range(n_runs)]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a built report dict as a Markdown string.

    Unknown / optional sections are simply absent from the
    rendered output.  Downstream workers can pipe the result
    into a PDF/PPTX converter.
    """
    lines: List[str] = []
    title = report.get("title", "Report")
    lines.append(f"# {title}")
    lines.append("")
    header = report.get("header") or {}
    if header:
        ps = header.get("period_start", report.get("period_start", ""))
        pe = header.get("period_end", report.get("period_end", ""))
        if ps or pe:
            lines.append(f"**Period:** {ps} → {pe}")
        rid = report.get("report_id")
        if rid:
            lines.append(f"**Report ID:** `{rid}`")
        lines.append("")

    if "design_summary" in report and report["design_summary"]:
        lines.append("## Design Summary")
        lines.append("")
        lines.append(str(report["design_summary"]))
        lines.append("")

    if "kpis" in report and report["kpis"]:
        lines.append("## KPIs")
        lines.append("")
        lines.append("| Name | Value | Delta |")
        lines.append("|------|-------|-------|")
        for k in report["kpis"]:
            lines.append(
                f"| {k.get('name', '')} | {k.get('value', '')} | {k.get('delta', '')} |"
            )
        lines.append("")

    if "metrics" in report and report["metrics"]:
        lines.append("## Metrics")
        lines.append("")
        for m in report["metrics"]:
            lines.append(
                f"- **{m.get('name', '')}** = {m.get('value', '')}"
                + (f" *(p={m.get('p_value'):.4g})*" if m.get("p_value") is not None else "")
            )
        lines.append("")

    if "decision" in report and report["decision"]:
        lines.append("## Decision")
        lines.append("")
        lines.append(f"**{report['decision']}**")
        lines.append("")

    if "anomalies" in report and report["anomalies"]:
        lines.append("## Anomalies")
        lines.append("")
        for a in report["anomalies"]:
            lines.append(f"- {a}")
        lines.append("")

    if "drift_signals" in report and report["drift_signals"]:
        lines.append("## Drift Signals")
        lines.append("")
        for s in report["drift_signals"]:
            lines.append(
                f"- {s.get('column', '?')}: "
                f"psi={s.get('psi', '')} "
                f"severity={s.get('severity', '')}"
            )
        lines.append("")

    if "retrain_recommendation" in report and report["retrain_recommendation"]:
        lines.append("## Retrain Recommendation")
        lines.append("")
        lines.append(str(report["retrain_recommendation"]))
        lines.append("")

    if (
        "protected_attribute_metrics" in report
        and report["protected_attribute_metrics"]
    ):
        lines.append("## Protected-attribute Metrics")
        lines.append("")
        lines.append("| Attribute | Group | Metric | Value |")
        lines.append("| --- | --- | --- | --- |")
        for row in report["protected_attribute_metrics"]:
            lines.append(
                f"| {row.get('attribute', '')} | {row.get('group', '')} | "
                f"{row.get('metric', '')} | {row.get('value', '')} |"
            )
        lines.append("")

    if "trends" in report and report["trends"]:
        lines.append("## Trends")
        lines.append("")
        for t in report["trends"]:
            lines.append(
                f"- {t.get('name', '')}: {t.get('direction', '')}"
            )
        lines.append("")

    if "next_steps" in report and report["next_steps"]:
        lines.append("## Next Steps")
        lines.append("")
        for s in report["next_steps"]:
            lines.append(f"- {s}")
        lines.append("")

    if "recommendations" in report and report["recommendations"]:
        lines.append("## Recommendations")
        lines.append("")
        for r in report["recommendations"]:
            lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "TEMPLATES",
    "get_template",
    "build_report",
    "compute_schedule",
    "render_markdown",
]


