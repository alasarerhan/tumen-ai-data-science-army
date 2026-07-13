# A1 — AB Testing Agent (Spec Implementation)

> Implements the first spec listed in `docs/AGENT_SPEC_CATALOG.md` (Section A, **P0**).
> Source catalog: [AGENT_SPEC_CATALOG.md](../AGENT_SPEC_CATALOG.md#a1--ab-testing-agent--p0)

## Status

✅ **Implemented** — initial scaffolding shipped.  All 7 statistical tools pass 24 unit tests; LangGraph agent class is wired and registered for discovery.

| Layer | File | Purpose |
| --- | --- | --- |
| Deterministic core | `ai_data_science_team/tools/ab_testing.py` | Pure-Python statistics, no LLM dependency, reusable from notebooks / runtime_engine |
| LangChain tool wrappers | `ai_data_science_team/agents/ab_testing_agent.py` | `@tool` + `InjectedState` wrappers |
| LangGraph agent | `ai_data_science_team/agents/ab_testing_agent.py` (`make_ab_testing_agent`, `ABTestingAgent`) | Same react-agent pattern as `EDAToolsAgent` / `DataQualityAgent` |
| Tests | `tests/test_ab_testing_tools.py` | 24 tests covering SRM, t/Welch/MWU, two-proportion z, CUPED, Bonferroni/BH, peeking, decision matrix, agent wiring, end-to-end |
| Demo | `examples/ab_testing_demo.py` | Synthetic experiment → full analysis without LLM |

## Capabilities

| # | Tool | Statistical Method |
| --- | --- | --- |
| 1 | `ab_check_srm` | Chi-square goodness-of-fit against expected split (default α=0.001) |
| 2 | `ab_analyze_continuous` | Welch's t-test (default) → Mann–Whitney U fallback when normality fails (Shapiro/D'Agostino) |
| 3 | `ab_analyze_proportion` | Two-proportion z-test + Wilson CIs |
| 4 | `ab_apply_cuped` | CUPED variance reduction with `theta = Cov(Y,X)/Var(X)` |
| 5 | `ab_correct_multiple` | Bonferroni / Benjamini–Hochberg FDR correction |
| 6 | `ab_detect_peeking` | Bonferroni-adjusted threshold across N interim looks |
| 7 | `ab_recommend_decision` | Ship / iterate / abort / watch based on p-value, MDE and sample ratio |

## Inputs (state)

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `data_raw` | dict | — | `pd.DataFrame.to_dict()` |
| `group_column` | str | `"group"` | Variant column |
| `expected_split` | dict \| None | `None` (equal split) | Proportions per variant |
| `alpha` | float | `0.05` | Significance level (SRM uses `0.001`) |

## Outputs (artifact → `analysis_results`)

```json
{
  "srm": {"srm_detected": false, "chi2": ..., "p_value": ..., "n_per_group": {...}},
  "metrics": [
    {"metric": "revenue", "test_used": "welch_t", "absolute_lift": ...,
     "ci_low": ..., "ci_high": ..., "p_value": ..., "effect_size": ...}
  ],
  "cuped": {"theta": ..., "variance_reduction_pct": ...},
  "multiple_comparison": {"method": "bh", "adjusted": [...], "rejected": [...]},
  "peeking": {"n_looks": ..., "bonferroni_threshold": ...,
              "naive_significant": ..., "bonferroni_significant": ...},
  "decision": {"decision": "ship", "rationale": "...", "mde_met": true}
}
```

## Usage

### Without an LLM (deterministic / scripted)

```python
from ai_data_science_team.tools.ab_testing import (
    check_sample_ratio_mismatch,
    analyze_continuous_metric,
    apply_cuped,
    recommend_decision,
)

srm = check_sample_ratio_mismatch(df, "group")
res = analyze_continuous_metric(df, "group", "revenue")
decision = recommend_decision(res, min_detectable_lift=0.02)
```

### With LangGraph (LLM-orchestrated)

```python
from langchain_openai import ChatOpenAI
from ai_data_science_team.agents import ABTestingAgent

llm = ChatOpenAI(model="gpt-4o-mini")
agent = ABTestingAgent(model=llm, group_column="variant")
agent.invoke_agent(
    data_raw=df,
    user_instructions="Analyse this conversion-rate experiment end-to-end.",
)
print(agent.get_srm())
print(agent.get_metric_results())
print(agent.get_decision())
```

### As a workflow node (`experiment.analyze`)

The agent exposes `NODE_TYPE = "experiment.analyze"` so the WorkflowResolver can
route `experiment.analyze` steps to it via capability matching.

## Decisions / Trade-offs

- **Auto test selection** for continuous metrics: normality test decides between
  Welch (parametric) and Mann–Whitney (non-parametric) instead of always running
  t-test.  Cheaper and more correct for skewed data.
- **Peeking guard**: chose a Bonferroni-corrected threshold (`alpha/n`) over the
  always-valid `alpha*e` lower bound.  Bonferroni is a more conservative and
  better-understood bound; an `alpha*e` lower bound is not actually a valid
  threshold under sequential testing — we removed that misleading artefact.
- **No `statsmodels` dependency**: only `numpy`, `scipy`, `pandas`.  Keeps the
  core lightweight and fast.
- **CUPED theta from overall data** (not per-arm).  This is the textbook CUPED
  formulation; per-arm theta is uncommon and statistically equivalent when
  treatment does not shift the covariate distribution.

## Limitations / Follow-ups

- Decision matrix does not yet consider guardrail metrics (catalog spec §A1
  mentions them).  These can be modelled as a separate `ab_check_guardrails`
  tool (see follow-up backlog below).
- Sequential testing uses Bonferroni, not mSPRT or alpha-spending.  Adequate as
  a warning; not a replacement for proper sequential designs.
- No stratified / clustered analysis yet (catalog spec hints at "stratification
  önerisi" — that lives in the Power Analysis & Experiment Design Agent, A2).

## Test status

```
$ pytest tests/test_ab_testing_tools.py -v
24 passed in ~3s
```