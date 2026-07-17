"""
AB Testing Agent — end-to-end demo (no LLM required).

Run with:
    python examples/ab_testing_demo.py

This script:
  1. Generates a synthetic experiment with a real +5% revenue lift.
  2. Runs each statistical tool from ``ai_data_science_team.tools.ab_testing``
     exactly the way the LLM-driven agent would.
  3. Prints a human-readable report.

The same orchestration is what ``ABTestingAgent.invoke_agent()`` triggers
via the LangGraph state graph + react tool-calling loop.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_data_science_team.tools.ab_testing import (
    analyze_continuous_metric,
    analyze_proportion_metric,
    apply_cuped,
    apply_multiple_comparison_correction,
    check_sample_ratio_mismatch,
    detect_sequential_peeking,
    recommend_decision,
)


def make_synthetic_experiment(n_per_arm: int = 5000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pre = rng.normal(loc=100, scale=20, size=n_per_arm)
    noise = rng.normal(loc=0, scale=10, size=n_per_arm)
    # Pre-experiment covariate and current-period metric share correlation
    # so CUPED has something to bite on.
    control = 0.8 * pre + noise + 50
    treatment = 0.8 * pre + noise + 52.5  # +5% mean vs control
    converted_control = rng.binomial(1, 0.10, size=n_per_arm)
    converted_treatment = rng.binomial(1, 0.115, size=n_per_arm)  # +1.5pp
    return pd.DataFrame(
        {
            "user_id": range(2 * n_per_arm),
            "group": ["control"] * n_per_arm + ["treatment"] * n_per_arm,
            "pre_metric": np.concatenate([pre, pre]),
            "revenue": np.concatenate([control, treatment]),
            "converted": np.concatenate([converted_control, converted_treatment]),
        }
    )


def main() -> None:
    df = make_synthetic_experiment()

    print("=" * 72)
    print("A1 — AB Testing Agent — Demo")
    print("=" * 72)

    # 1) SRM
    srm = check_sample_ratio_mismatch(df, "group")
    print(f"\n[1] SRM check: {'DETECTED' if srm['srm_detected'] else 'OK'}")
    print(f"    Counts: {srm['n_per_group']}, chi2={srm['chi2']:.3f}, p={srm['p_value']:.4f}")

    # 2) Continuous metric
    rev = analyze_continuous_metric(df, "group", "revenue")
    print("\n[2] Revenue (continuous):")
    print(f"    control={rev['control_mean']:.3f} → treatment={rev['treatment_mean']:.3f}")
    print(f"    lift={rev['relative_lift']:.2%}, "
          f"CI=[{rev['ci_low']:.3f}, {rev['ci_high']:.3f}], "
          f"p={rev['p_value']:.4f} ({rev['test_used']})")
    print(f"    Cohen's d = {rev['effect_size']:.3f}")

    # 3) Proportion metric
    conv = analyze_proportion_metric(df, "group", "converted")
    print("\n[3] Conversion (proportion):")
    print(f"    control={conv['control_mean']:.3%} → treatment={conv['treatment_mean']:.3%}")
    print(f"    lift={conv['relative_lift']:.2%}, p={conv['p_value']:.4f}, "
          f"z={conv['z_stat']:.2f}")

    # 4) CUPED
    cuped = apply_cuped(df, "group", "revenue", "pre_metric")
    print("\n[4] CUPED variance reduction:")
    print(f"    theta={cuped['theta']:.3f}, "
          f"variance reduction={cuped['variance_reduction_pct']:.1f}%")
    print(f"    adjusted lift={cuped['absolute_lift_adjusted']:.3f}")

    # 5) Multiple-comparison correction
    mcc = apply_multiple_comparison_correction(
        [rev["p_value"], conv["p_value"]], method="bh"
    )
    print("\n[5] BH correction across 2 metrics:")
    print(f"    adjusted p = {mcc['adjusted']}, rejected = {mcc['rejected']}")

    # 6) Sequential peeking (simulated: 5 daily interim looks)
    seq_p = [0.30, 0.12, 0.08, 0.06, 0.045]  # analyst peeked daily
    peeking = detect_sequential_peeking(seq_p, alpha=0.05)
    print("\n[6] Sequential peeking (5 interim looks):")
    print(f"    {peeking['peeking_warning']}")

    # 7) Decision
    decision = recommend_decision(
        rev,
        min_detectable_lift=0.02,  # 2% MDE
        required_sample_ratio=1.0,
    )
    print("\n[7] Final decision:")
    print(f"    {decision['decision'].upper()}: {decision['rationale']}")
    print()


if __name__ == "__main__":
    main()