from __future__ import annotations

"""Strategic Insights tools — M18.

Pure-Python tools for the four Strategic Supervisor agents:

**ResultsSynthesizer group** (4 tools)
    ``merge_agent_outputs``         — merge multiple agent artifact dicts
    ``extract_key_metrics``         — filter a specific metric from merged results
    ``compare_results``             — delta / improvement between baseline and current
    ``rank_findings``               — sort findings by a chosen criterion

**ContextualKnowledge group** (3 tools)
    ``build_context_profile``       — create a structured business context record
    ``generate_clarifying_questions`` — produce targeted questions for the user
    ``extract_business_entities``   — pull KPIs, goals, teams, products from text

**Narrative group** (3 tools)
    ``generate_executive_summary``  — prose executive summary from findings
    ``generate_section``            — single numbered report section
    ``format_report``               — assemble sections into a full report

**Recommendation group** (3 tools)
    ``generate_recommendations``    — ranked action items from findings + context
    ``design_ab_test``              — A/B test plan for a hypothesis
    ``prioritize_actions``          — ICE-scored priority order for actions

All tools use ``response_format="content_and_artifact"`` and return
``Tuple[str, Dict[str, Any]]`` so they work seamlessly in ReAct tool-calling
loops without needing an external API.
"""
import json  # noqa: E402, F401
from typing import Any, Dict, List, Tuple  # noqa: E402, F401

from langchain_core.tools import tool  # noqa: E402, F401

# ===========================================================================
# ResultsSynthesizer group
# ===========================================================================


@tool(response_format="content_and_artifact")
def merge_agent_outputs(outputs_json: str) -> Tuple[str, Dict[str, Any]]:
    """Merge artifact dictionaries from multiple agents into a unified results map.

    Parameters
    ----------
    outputs_json : str
        JSON-encoded mapping of ``{agent_name: artifact_dict}``.
        Example: ``'{"ClusteringAgent": {"n_clusters": 3, "silhouette": 0.61}}'``

    Returns
    -------
    text : str
        Human-readable summary of merged keys.
    artifact : dict
        ``{merged: dict, agent_count: int, total_keys: int}``
    """
    try:
        raw: Dict[str, Any] = json.loads(outputs_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return (
            f"❌ Invalid JSON: {exc}",
            {"merged": {}, "agent_count": 0, "total_keys": 0, "valid": False},
        )

    merged: Dict[str, Any] = {}
    for agent_name, artifact in raw.items():
        if isinstance(artifact, dict):
            for k, v in artifact.items():
                merged[f"{agent_name}.{k}"] = v
        else:
            merged[agent_name] = artifact

    lines = [f"• {k}: {v}" for k, v in list(merged.items())[:20]]
    if len(merged) > 20:
        lines.append(f"  … (+{len(merged) - 20} more keys)")

    text = f"✅ Merged {len(raw)} agent output(s) → {len(merged)} total keys.\n\n" + "\n".join(
        lines
    )
    return text, {
        "merged": merged,
        "agent_count": len(raw),
        "total_keys": len(merged),
        "valid": True,
    }


@tool(response_format="content_and_artifact")
def extract_key_metrics(
    merged_json: str,
    metric_keys: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """Extract specific metric keys from a merged results dict.

    Parameters
    ----------
    merged_json : str
        JSON string representing a flat ``{key: value}`` dict (as returned by
        ``merge_agent_outputs.artifact["merged"]``).
    metric_keys : str
        Comma-separated list of partial key names to keep.
        Example: ``"silhouette,rmse,accuracy"``
        If empty, all keys are returned.

    Returns
    -------
    text : str
        Human-readable list of extracted metrics.
    artifact : dict
        ``{metrics: dict, requested: list, found: int}``
    """
    try:
        merged: Dict[str, Any] = json.loads(merged_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return (
            f"❌ Invalid JSON: {exc}",
            {"metrics": {}, "requested": [], "found": 0, "valid": False},
        )

    requested = [k.strip() for k in metric_keys.split(",") if k.strip()]

    if requested:
        extracted = {
            k: v for k, v in merged.items() if any(req.lower() in k.lower() for req in requested)
        }
    else:
        extracted = dict(merged)

    lines = [f"  {k} = {v}" for k, v in extracted.items()]
    text = f"📊 Extracted {len(extracted)} metric(s):\n" + ("\n".join(lines) or "  (none found)")
    return text, {
        "metrics": extracted,
        "requested": requested,
        "found": len(extracted),
        "valid": True,
    }


@tool(response_format="content_and_artifact")
def compare_results(
    baseline_json: str,
    current_json: str,
    higher_is_better: str = "accuracy,silhouette,r2,f1",
    lower_is_better: str = "rmse,mae,mape,error,loss",
) -> Tuple[str, Dict[str, Any]]:
    """Compare two result sets (baseline vs current) and report deltas.

    Parameters
    ----------
    baseline_json : str
        JSON ``{metric: value}`` for the baseline / previous model.
    current_json : str
        JSON ``{metric: value}`` for the current / new model.
    higher_is_better : str
        Comma-separated metric substrings where a higher value is better.
    lower_is_better : str
        Comma-separated metric substrings where a lower value is better.

    Returns
    -------
    text : str
        Delta report with improvement/regression indicators.
    artifact : dict
        ``{deltas: dict, improvements: list, regressions: list}``
    """
    try:
        baseline: Dict[str, Any] = json.loads(baseline_json)
        current: Dict[str, Any] = json.loads(current_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return (
            f"❌ Invalid JSON: {exc}",
            {"deltas": {}, "improvements": [], "regressions": [], "valid": False},
        )

    hib = [x.strip().lower() for x in higher_is_better.split(",") if x.strip()]
    lib = [x.strip().lower() for x in lower_is_better.split(",") if x.strip()]

    common_keys = set(baseline) & set(current)
    deltas: Dict[str, Any] = {}
    improvements: List[str] = []
    regressions: List[str] = []
    lines = []

    for k in sorted(common_keys):
        b_val = baseline[k]
        c_val = current[k]
        try:
            delta = float(c_val) - float(b_val)
            pct = (delta / float(b_val) * 100) if float(b_val) != 0 else 0.0
            k_low = k.lower()
            is_hib = any(h in k_low for h in hib)
            is_lib = any(label in k_low for label in lib)
            if is_hib:
                good = delta > 0
            elif is_lib:
                good = delta < 0
            else:
                good = None

            icon = "✅" if good is True else ("⚠️" if good is False else "➡️")
            if good is True:
                improvements.append(k)
            elif good is False:
                regressions.append(k)

            deltas[k] = {
                "baseline": b_val,
                "current": c_val,
                "delta": round(delta, 4),
                "pct": round(pct, 2),
            }
            lines.append(f"  {icon} {k}: {b_val} → {c_val} (Δ {delta:+.4f}, {pct:+.1f}%)")
        except (TypeError, ValueError):
            deltas[k] = {"baseline": b_val, "current": c_val, "delta": None}
            lines.append(f"  ➡️ {k}: {b_val} → {c_val}")

    text = (
        f"📈 Comparison — {len(improvements)} improvement(s), {len(regressions)} regression(s)\n"
        + "\n".join(lines)
    )
    return text, {
        "deltas": deltas,
        "improvements": improvements,
        "regressions": regressions,
        "metrics_compared": len(common_keys),
        "valid": True,
    }


@tool(response_format="content_and_artifact")
def rank_findings(
    findings_json: str,
    sort_by: str = "impact",
    descending: bool = True,
    top_n: int = 10,
) -> Tuple[str, Dict[str, Any]]:
    """Rank a list of finding dicts by a chosen numeric field.

    Parameters
    ----------
    findings_json : str
        JSON list of dicts, each dict representing a finding.
        Each dict should have at least a ``"description"`` and a numeric field
        whose name matches ``sort_by``.  Example::

            '[{"description": "Churn risk up", "impact": 0.8, "confidence": 0.9}]'

    sort_by : str
        Key to sort by.  Defaults to ``"impact"``.
    descending : bool
        Sort high → low when True (default).
    top_n : int
        Maximum number of ranked findings to return.

    Returns
    -------
    text : str
        Numbered ranked list.
    artifact : dict
        ``{ranked: list, sort_by: str, total: int}``
    """
    try:
        findings: List[Dict[str, Any]] = json.loads(findings_json)
        if not isinstance(findings, list):
            raise ValueError("Expected a JSON array")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return (
            f"❌ Invalid JSON: {exc}",
            {"ranked": [], "sort_by": sort_by, "total": 0, "valid": False},
        )

    def _sort_key(f: Dict[str, Any]) -> float:
        val = f.get(sort_by, 0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    ranked = sorted(findings, key=_sort_key, reverse=descending)[:top_n]
    lines = []
    for i, f in enumerate(ranked, 1):
        desc = f.get("description", str(f))
        score = f.get(sort_by, "—")
        lines.append(f"  {i}. [{sort_by}={score}] {desc}")

    text = f"🏆 Top {len(ranked)} findings ranked by '{sort_by}':\n" + "\n".join(lines)
    return text, {"ranked": ranked, "sort_by": sort_by, "total": len(findings), "valid": True}


# ===========================================================================
# ContextualKnowledge group
# ===========================================================================


@tool(response_format="content_and_artifact")
def build_context_profile(
    company_name: str = "Unknown",
    industry: str = "General",
    goal: str = "",
    time_horizon: str = "short-term",
    kpis: str = "",
    audience: str = "executive",
) -> Tuple[str, Dict[str, Any]]:
    """Build a structured business context profile for downstream agents.

    Parameters
    ----------
    company_name : str
        Name of the company / organisation.
    industry : str
        Industry vertical (e.g. ``"e-commerce"``, ``"fintech"``).
    goal : str
        Primary business goal of the analysis.
    time_horizon : str
        Planning horizon: ``"short-term"`` (< 3 months), ``"medium-term"``
        (3–12 months), or ``"long-term"`` (> 12 months).
    kpis : str
        Comma-separated list of relevant KPIs.
    audience : str
        Intended report audience: ``"executive"``, ``"technical"``, or ``"operational"``.

    Returns
    -------
    text : str
        Formatted context summary.
    artifact : dict
        Structured context profile.
    """
    kpi_list = [k.strip() for k in kpis.split(",") if k.strip()]
    profile: Dict[str, Any] = {
        "company_name": company_name,
        "industry": industry,
        "goal": goal or "Not specified",
        "time_horizon": time_horizon,
        "kpis": kpi_list,
        "audience": audience,
    }
    kpi_str = ", ".join(kpi_list) if kpi_list else "None specified"
    text = (
        f"📋 Business Context Profile\n"
        f"  Company     : {company_name}\n"
        f"  Industry    : {industry}\n"
        f"  Goal        : {profile['goal']}\n"
        f"  Time Horizon: {time_horizon}\n"
        f"  KPIs        : {kpi_str}\n"
        f"  Audience    : {audience}"
    )
    return text, profile


@tool(response_format="content_and_artifact")
def generate_clarifying_questions(
    analysis_summary: str,
    num_questions: int = 5,
    focus_area: str = "business_impact",
) -> Tuple[str, Dict[str, Any]]:
    """Generate targeted clarifying questions to improve analysis context.

    Parameters
    ----------
    analysis_summary : str
        Brief description of what has been analysed so far.
    num_questions : int
        Number of questions to generate (1–10).
    focus_area : str
        Focus of the questions: ``"business_impact"``, ``"technical"``,
        ``"audience"``, or ``"scope"``.

    Returns
    -------
    text : str
        Numbered list of questions.
    artifact : dict
        ``{questions: list, focus_area: str, count: int}``
    """
    num_questions = max(1, min(10, num_questions))

    _QUESTION_TEMPLATES: Dict[str, List[str]] = {
        "business_impact": [
            "What is the estimated revenue impact of the key findings?",
            "Which business unit will be most affected by these results?",
            "What is the acceptable risk threshold for recommended actions?",
            "Are there regulatory or compliance constraints that affect implementation?",
            "What is the expected ROI timeline for the proposed changes?",
            "Who are the primary stakeholders that need to approve these recommendations?",
            "What parallel initiatives might conflict or align with these findings?",
            "Is there a preferred prioritisation framework (e.g. RICE, ICE, MoSCoW)?",
            "What does success look like in 90 days?",
            "Are there budget constraints for the recommended actions?",
        ],
        "technical": [
            "What data refresh frequency is required for ongoing monitoring?",
            "Are there integration requirements with existing systems?",
            "What are the data quality SLAs for the key metrics?",
            "Which model performance thresholds are acceptable for production?",
            "What monitoring and alerting needs to be set up post-deployment?",
            "Are there latency requirements for real-time scoring?",
            "What is the model retraining cadence?",
            "Are there on-premise vs cloud deployment preferences?",
            "What logging and audit trail requirements apply?",
            "What security and access-control constraints apply?",
        ],
        "audience": [
            "What level of technical detail is appropriate for the primary audience?",
            "Should visualisations be interactive or static?",
            "Are there specific terminology preferences in this organisation?",
            "What format is preferred: slide deck, PDF report, or dashboard?",
            "How frequently should progress updates be communicated?",
        ],
        "scope": [
            "Are there additional data sources that should be incorporated?",
            "Should the analysis be extended to other market segments?",
            "What time period should be used as the historical baseline?",
            "Are there geographic or product-line filters to apply?",
            "Should competitors or benchmarks be included in the analysis?",
        ],
    }

    templates = _QUESTION_TEMPLATES.get(focus_area, _QUESTION_TEMPLATES["business_impact"])
    questions = templates[:num_questions]

    lines = [f"  {i}. {q}" for i, q in enumerate(questions, 1)]
    text = (
        f"❓ {len(questions)} clarifying question(s) [{focus_area}]:\n"
        f"  (Context: {analysis_summary[:120]}{'…' if len(analysis_summary) > 120 else ''})\n\n"
        + "\n".join(lines)
    )
    return text, {"questions": questions, "focus_area": focus_area, "count": len(questions)}


@tool(response_format="content_and_artifact")
def extract_business_entities(
    text: str,
    entity_types: str = "kpi,team,product,goal,metric",
) -> Tuple[str, Dict[str, Any]]:
    """Extract business entities (KPIs, teams, products, goals) from free text.

    Uses simple heuristics and keyword matching suitable for offline use.

    Parameters
    ----------
    text : str
        Free-form business text (meeting notes, reports, strategy docs, etc.).
    entity_types : str
        Comma-separated entity categories to extract.  Supported values:
        ``kpi``, ``team``, ``product``, ``goal``, ``metric``.

    Returns
    -------
    text_out : str
        Formatted entity extraction report.
    artifact : dict
        ``{entities: {type: [values]}, total: int}``
    """
    import re  # noqa: E402, F401

    requested_types = {t.strip().lower() for t in entity_types.split(",") if t.strip()}

    _PATTERNS: Dict[str, str] = {
        "kpi": r"\b(?:KPI|kpi|metric|measure|rate|ratio|score|index|NPS|CSAT|ARR|MRR|CLV|CAC|ROI|ROAS|CTR|CVR|churn|retention|revenue|profit|margin|uplift|lift)\b\s*[\w\s]{0,30}",
        "team": r"\b(?:team|squad|tribe|chapter|department|division|unit|group)\s+\w+|\w+\s+(?:team|squad|tribe|department|division)\b",
        "product": r"\b(?:product|service|feature|platform|app|application|module|component|API|SDK)\s+\w+|\w+\s+(?:product|service|platform|app)\b",
        "goal": r"\b(?:goal|objective|OKR|target|aim|initiative|priority|roadmap item)\s*:?\s*[\w\s]{0,50}",
        "metric": r"\b\d+(?:\.\d+)?(?:\s*%|\s*x|\s*USD|\s*EUR|\s*k|\s*M|\s*B)?\b",
    }

    entities: Dict[str, List[str]] = {}
    for etype in requested_types:
        pattern = _PATTERNS.get(etype)
        if pattern:
            matches = re.findall(pattern, text, re.IGNORECASE)
            cleaned = list({m.strip() for m in matches if len(m.strip()) > 2})
            entities[etype] = cleaned[:15]

    total = sum(len(v) for v in entities.values())
    lines = []
    for etype, vals in entities.items():
        lines.append(f"  [{etype.upper()}]: {', '.join(vals[:5]) if vals else 'none found'}")

    text_out = f"🔍 Extracted {total} business entity mention(s):\n" + "\n".join(lines)
    return text_out, {
        "entities": entities,
        "total": total,
        "requested_types": list(requested_types),
    }


# ===========================================================================
# Narrative group
# ===========================================================================

_TONE_STYLES: Dict[str, str] = {
    "executive": "concise, strategic, and results-focused",
    "technical": "precise, data-driven, and methodologically rigorous",
    "operational": "practical, action-oriented, and step-by-step",
}

_SECTION_GUIDANCES: Dict[str, str] = {
    "findings": "Summarise the key analytical findings in plain language. Lead with the most important result. Use bullet points where appropriate.",
    "methodology": "Explain the analytical approach used: data sources, algorithms, feature engineering, and model selection criteria.",
    "risks": "Identify the top risks, assumptions, and limitations of the analysis. Rate each HIGH / MEDIUM / LOW.",
    "next_steps": "Propose 3–5 concrete next steps with owners, deadlines, and success criteria.",
    "appendix": "Include detailed tables, model parameters, and technical notes for the technical reader.",
    "context": "Describe the business context: company, industry, strategic goals, and relevant market trends.",
    "recommendations": "Present ranked, actionable recommendations with expected impact and implementation effort.",
}


@tool(response_format="content_and_artifact")
def generate_executive_summary(
    findings_json: str,
    context_json: str = "{}",
    tone: str = "executive",
    max_words: int = 200,
) -> Tuple[str, Dict[str, Any]]:
    """Generate a prose executive summary from analysis findings and business context.

    Parameters
    ----------
    findings_json : str
        JSON list or dict of key findings (e.g. from ``rank_findings`` artifact).
    context_json : str
        JSON context profile (e.g. from ``build_context_profile`` artifact).
    tone : str
        Writing tone: ``"executive"``, ``"technical"``, or ``"operational"``.
    max_words : int
        Approximate target word count for the summary (50–500).

    Returns
    -------
    text : str
        The executive summary prose.
    artifact : dict
        ``{summary: str, tone: str, word_count: int}``
    """
    max_words = max(50, min(500, max_words))

    try:
        findings = json.loads(findings_json)
    except (json.JSONDecodeError, TypeError):
        findings = {"raw": findings_json}

    try:
        context: Dict[str, Any] = json.loads(context_json)
    except (json.JSONDecodeError, TypeError):
        context = {}

    tone_style = _TONE_STYLES.get(tone, _TONE_STYLES["executive"])

    company = context.get("company_name", "the organisation")
    industry = context.get("industry", "the industry")
    goal = context.get("goal", "improve business performance")
    audience = context.get("audience", "executive")
    kpis = context.get("kpis", [])
    kpi_str = (", ".join(str(k) for k in kpis[:3]) + " ") if kpis else ""

    # Build findings excerpt
    if isinstance(findings, list):
        top = findings[:3]
        findings_text = "; ".join(
            str(f.get("description", f)) if isinstance(f, dict) else str(f) for f in top
        )
        n_findings = len(findings)
    elif isinstance(findings, dict):
        ranked = findings.get("ranked", [])
        if ranked:
            top = ranked[:3]
            findings_text = "; ".join(
                str(f.get("description", f)) if isinstance(f, dict) else str(f) for f in top
            )
            n_findings = findings.get("total", len(ranked))
        else:
            findings_text = "; ".join(f"{k}: {v}" for k, v in list(findings.items())[:3])
            n_findings = len(findings)
    else:
        findings_text = str(findings)[:200]
        n_findings = 1

    summary = (
        f"This analysis was conducted for {company} within the {industry} sector "
        f"with the objective to {goal}. "
        f"The study synthesised results across {n_findings} key finding(s), "
        f"including {findings_text}. "
        f"{'Key performance indicators monitored include ' + kpi_str + '.' if kpis else ''} "
        f"The report is written in a {tone_style} style and is intended for a "
        f"{audience}-level audience. "
        f"A set of prioritised recommendations follows, designed to drive measurable "
        f"improvement in the identified areas within the specified time horizon."
    )

    # Trim roughly to max_words
    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]) + "…"

    return summary, {
        "summary": summary,
        "tone": tone,
        "word_count": len(summary.split()),
        "company": company,
        "n_findings": n_findings,
    }


@tool(response_format="content_and_artifact")
def generate_section(
    section_type: str,
    data_json: str = "{}",
    tone: str = "executive",
    title: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """Generate a single named report section with guidance text and data summary.

    Parameters
    ----------
    section_type : str
        One of: ``findings``, ``methodology``, ``risks``, ``next_steps``,
        ``appendix``, ``context``, ``recommendations``.
    data_json : str
        JSON data to summarise inside the section.
    tone : str
        Writing tone: ``"executive"``, ``"technical"``, or ``"operational"``.
    title : str
        Optional custom section title (overrides default).

    Returns
    -------
    text : str
        The formatted Markdown section.
    artifact : dict
        ``{section_type: str, title: str, content: str, tone: str}``
    """
    guidance = _SECTION_GUIDANCES.get(
        section_type.lower(),
        "Provide a clear, structured narrative for this section.",
    )
    tone_style = _TONE_STYLES.get(tone, _TONE_STYLES["executive"])

    try:
        data = json.loads(data_json)
    except (json.JSONDecodeError, TypeError):
        data = {}

    section_title = title or section_type.replace("_", " ").title()

    # Build data summary snippet
    if isinstance(data, dict) and data:
        data_lines = [f"  - {k}: {v}" for k, v in list(data.items())[:8]]
        data_block = "\n" + "\n".join(data_lines)
    elif isinstance(data, list) and data:
        data_lines = [f"  - {item}" for item in data[:8]]
        data_block = "\n" + "\n".join(data_lines)
    else:
        data_block = "\n  *(No structured data provided — please fill in manually.)*"

    content = f"## {section_title}\n\n*Guidance ({tone_style}): {guidance}*\n{data_block}\n"

    return content, {
        "section_type": section_type,
        "title": section_title,
        "content": content,
        "tone": tone,
        "data_keys": list(data.keys()) if isinstance(data, dict) else [],
    }


@tool(response_format="content_and_artifact")
def format_report(
    sections_json: str,
    title: str = "Strategic Insights Report",
    format_type: str = "markdown",
    include_toc: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """Assemble individual sections into a complete report document.

    Parameters
    ----------
    sections_json : str
        JSON list of section content strings (as returned by ``generate_section``
        artifact ``content`` fields), or a list of plain text sections.
    title : str
        Report title.
    format_type : str
        Output format: ``"markdown"`` (default) or ``"plain"``.
    include_toc : bool
        Whether to prepend a table of contents.

    Returns
    -------
    text : str
        The assembled report text.
    artifact : dict
        ``{report: str, title: str, section_count: int, format_type: str}``
    """
    try:
        sections: List[str] = json.loads(sections_json)
        if not isinstance(sections, list):
            sections = [str(sections)]
    except (json.JSONDecodeError, TypeError):
        sections = [sections_json]

    if format_type == "markdown":
        header = f"# {title}\n\n---\n\n"
    else:
        header = f"{title.upper()}\n{'=' * len(title)}\n\n"

    toc_lines: List[str] = []
    if include_toc and format_type == "markdown":
        toc_lines.append("## Table of Contents\n")
        for i, sec in enumerate(sections, 1):
            # Extract first heading from section
            first_line = sec.strip().splitlines()[0] if sec.strip() else f"Section {i}"
            heading = first_line.lstrip("#").strip() or f"Section {i}"
            anchor = heading.lower().replace(" ", "-").replace("(", "").replace(")", "")
            toc_lines.append(f"  {i}. [{heading}](#{anchor})")
        header += "\n".join(toc_lines) + "\n\n---\n\n"

    body = "\n\n---\n\n".join(s.strip() for s in sections)
    report = header + body

    return report, {
        "report": report,
        "title": title,
        "section_count": len(sections),
        "format_type": format_type,
        "include_toc": include_toc,
    }


# ===========================================================================
# Recommendation group
# ===========================================================================


@tool(response_format="content_and_artifact")
def generate_recommendations(
    findings_json: str,
    context_json: str = "{}",
    num_recommendations: int = 5,
    effort_scale: str = "low,medium,high",
) -> Tuple[str, Dict[str, Any]]:
    """Generate ranked, actionable business recommendations from findings.

    Parameters
    ----------
    findings_json : str
        JSON list/dict of findings (e.g. from ``rank_findings``).
    context_json : str
        JSON context profile (e.g. from ``build_context_profile``).
    num_recommendations : int
        Number of recommendations to generate (1–10).
    effort_scale : str
        Comma-separated effort levels to assign (cycles through the list).

    Returns
    -------
    text : str
        Numbered recommendation list.
    artifact : dict
        ``{recommendations: list, count: int}``
    """
    num_recommendations = max(1, min(10, num_recommendations))

    try:
        findings = json.loads(findings_json)
    except (json.JSONDecodeError, TypeError):
        findings = {}

    try:
        context: Dict[str, Any] = json.loads(context_json)
    except (json.JSONDecodeError, TypeError):
        context = {}

    efforts = [e.strip() for e in effort_scale.split(",") if e.strip()] or ["medium"]
    goal = context.get("goal", "improve business performance")
    company = context.get("company_name", "the organisation")
    industry = context.get("industry", "the industry")
    horizon = context.get("time_horizon", "short-term")

    # Build finding descriptions list
    if isinstance(findings, list):
        descs = [
            (f.get("description", str(f)) if isinstance(f, dict) else str(f))
            for f in findings[:num_recommendations]
        ]
    elif isinstance(findings, dict):
        ranked = findings.get("ranked", [])
        if ranked:
            descs = [
                (f.get("description", str(f)) if isinstance(f, dict) else str(f))
                for f in ranked[:num_recommendations]
            ]
        else:
            descs = [f"{k}: {v}" for k, v in list(findings.items())[:num_recommendations]]
    else:
        descs = [str(findings)]

    _IMPACT_LEVELS = ["high", "high", "medium", "medium", "low"]
    _ACTION_TEMPLATES = [
        "Immediately address: {desc} — assign a dedicated workstream with clear KPIs.",
        "Prioritise: {desc} — run a 2-week pilot before full roll-out.",
        "Investigate: {desc} — commission deeper analysis to confirm the hypothesis.",
        "Monitor: {desc} — set up automated alerts on the relevant metrics.",
        "Plan: {desc} — include in the next quarterly roadmap review.",
    ]

    recommendations: List[Dict[str, Any]] = []
    for i, desc in enumerate(descs):
        effort = efforts[i % len(efforts)]
        impact = _IMPACT_LEVELS[i % len(_IMPACT_LEVELS)]
        template = _ACTION_TEMPLATES[i % len(_ACTION_TEMPLATES)]
        action = template.format(desc=desc[:120])
        recommendations.append(
            {
                "rank": i + 1,
                "action": action,
                "impact": impact,
                "effort": effort,
                "time_horizon": horizon,
                "source_finding": desc[:120],
            }
        )

    lines = [
        f"  {r['rank']}. [{r['impact'].upper()} impact / {r['effort']} effort] {r['action']}"
        for r in recommendations
    ]
    text = (
        f"💡 {len(recommendations)} recommendation(s) for {company} ({industry}, {goal}):\n"
        + "\n".join(lines)
    )
    return text, {"recommendations": recommendations, "count": len(recommendations), "goal": goal}


@tool(response_format="content_and_artifact")
def design_ab_test(
    hypothesis: str,
    primary_metric: str,
    expected_effect_pct: float = 5.0,
    audience_size: int = 10000,
    confidence_level: float = 0.95,
    test_duration_days: int = 14,
) -> Tuple[str, Dict[str, Any]]:
    """Generate a complete A/B test design plan for a business hypothesis.

    Parameters
    ----------
    hypothesis : str
        The hypothesis to test. Example: ``"Showing social proof increases checkout CVR"``
    primary_metric : str
        The metric to measure. Example: ``"checkout_conversion_rate"``
    expected_effect_pct : float
        Expected relative lift in percent (e.g. ``5.0`` = 5% improvement).
    audience_size : int
        Total number of users available for the experiment.
    confidence_level : float
        Statistical confidence level (e.g. ``0.95`` for 95%).
    test_duration_days : int
        Planned test duration in days.

    Returns
    -------
    text : str
        Formatted A/B test plan.
    artifact : dict
        Full test plan dict.
    """
    import math  # noqa: E402, F401

    # Simple sample size estimate (rule of thumb: ~16 * σ² / δ²; assume σ≈baseline)
    alpha = 1.0 - confidence_level
    # z-score for two-tailed test
    z_table = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_table.get(round(confidence_level, 2), 1.96)
    rel_delta = expected_effect_pct / 100.0
    # Estimate required n per variant (rough approximation)
    n_per_variant = max(100, int(math.ceil((2 * z**2 * 0.25) / (rel_delta**2))))
    n_total = n_per_variant * 2
    feasible = audience_size >= n_total

    plan: Dict[str, Any] = {
        "hypothesis": hypothesis,
        "primary_metric": primary_metric,
        "expected_effect_pct": expected_effect_pct,
        "confidence_level": confidence_level,
        "alpha": round(alpha, 4),
        "z_score": z,
        "n_per_variant": n_per_variant,
        "n_total_required": n_total,
        "audience_size": audience_size,
        "feasible": feasible,
        "test_duration_days": test_duration_days,
        "control": "Existing experience (no change)",
        "treatment": f"Modified experience to validate: {hypothesis}",
        "success_criteria": (
            f"Statistically significant improvement in {primary_metric} "
            f"of ≥ {expected_effect_pct:.1f}% at {confidence_level * 100:.0f}% confidence"
        ),
        "guardrail_metrics": ["revenue_per_user", "bounce_rate", "support_tickets"],
    }

    status = "✅ FEASIBLE" if feasible else "⚠️  UNDER-POWERED (audience too small)"
    text = (
        f"🧪 A/B Test Plan — {status}\n"
        f"  Hypothesis    : {hypothesis}\n"
        f"  Primary Metric: {primary_metric}\n"
        f"  Expected Lift : {expected_effect_pct:.1f}%\n"
        f"  Confidence    : {confidence_level * 100:.0f}%  (z={z})\n"
        f"  Required n    : {n_total:,} total ({n_per_variant:,} per variant)\n"
        f"  Available n   : {audience_size:,}\n"
        f"  Duration      : {test_duration_days} days\n"
        f"  Success       : {plan['success_criteria']}"
    )
    return text, plan


@tool(response_format="content_and_artifact")
def prioritize_actions(
    actions_json: str,
    framework: str = "ice",
) -> Tuple[str, Dict[str, Any]]:
    """Score and prioritise a list of actions using ICE or RICE frameworks.

    Parameters
    ----------
    actions_json : str
        JSON list of action dicts.  Each dict should contain at minimum a
        ``"description"`` field.  For ICE scoring it may include
        ``"impact"`` (1–10), ``"confidence"`` (1–10), ``"ease"`` (1–10).
        For RICE: ``"reach"`` (users), ``"impact"`` (0.25–3), ``"confidence"``
        (0–100), ``"effort"`` (person-months).
    framework : str
        Scoring framework: ``"ice"`` (default) or ``"rice"``.

    Returns
    -------
    text : str
        Ranked action table.
    artifact : dict
        ``{prioritized: list, framework: str, count: int}``
    """
    try:
        actions: List[Dict[str, Any]] = json.loads(actions_json)
        if not isinstance(actions, list):
            raise ValueError("Expected a JSON array")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return (
            f"❌ Invalid JSON: {exc}",
            {"prioritized": [], "framework": framework, "count": 0, "valid": False},
        )

    scored: List[Dict[str, Any]] = []
    for action in actions:
        a = dict(action)
        desc = a.get("description", str(a))

        if framework.lower() == "rice":
            reach = float(a.get("reach", 1000))
            impact = float(a.get("impact", 1.0))
            confidence = float(a.get("confidence", 80)) / 100.0
            effort = float(a.get("effort", 1.0))
            score = (reach * impact * confidence) / max(effort, 0.01)
            a["rice_score"] = round(score, 2)
        else:  # ice
            impact = float(a.get("impact", 5))
            confidence = float(a.get("confidence", 5))
            ease = float(a.get("ease", 5))
            score = (impact * confidence * ease) / 100.0
            a["ice_score"] = round(score, 3)

        a["_sort_score"] = score
        a["description"] = desc
        scored.append(a)

    scored.sort(key=lambda x: x["_sort_score"], reverse=True)
    for i, a in enumerate(scored, 1):
        a["priority_rank"] = i

    score_key = "rice_score" if framework.lower() == "rice" else "ice_score"
    lines = [
        f"  {a['priority_rank']}. [score={a.get(score_key, '?')}] {a['description'][:80]}"
        for a in scored
    ]
    text = f"🎯 {len(scored)} action(s) prioritised using {framework.upper()}:\n" + "\n".join(lines)
    return text, {
        "prioritized": scored,
        "framework": framework,
        "count": len(scored),
        "valid": True,
    }
