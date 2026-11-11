"""Robustness checks for the Medicaid expansion difference-in-differences.

1. Joint test that the pre-period event-study coefficients (2008-2012) are all zero.
2. Leave-one-state-out: re-estimate the simple DiD dropping each state in turn.
3. Placebo: pretend expansion happened in 2010, using only 2008-2013 data.
4. Drop DC, the only treated jurisdiction that is not a state.

Output: data/output/robustness.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import event_study as es

RATES = Path("data/interim/state_year_rates.csv")
OUT = Path("data/output/robustness.csv")
PRE_YEARS = [2008, 2009, 2010, 2011, 2012]


def simple_did(panel: pd.DataFrame, post_year: int = es.EXPANSION_YEAR) -> tuple[float, float, float]:
    """Return (estimate, ci_low, ci_high) for the post x treated term."""
    panel = panel.copy()
    panel["post"] = (panel["year"] >= post_year).astype(float)
    res = es.fit(panel, event_study=False)
    low, high = res.conf_int().loc["treated_x_post"]
    return float(res.params["treated_x_post"]), float(low), float(high)


def pre_trend_test(panel: pd.DataFrame) -> tuple[float, float]:
    """Joint Wald test that the 2008-2012 event-study coefficients are zero."""
    res = es.fit(panel, event_study=True)
    names = [f"treated_x_{y}" for y in PRE_YEARS]
    R = np.zeros((len(names), len(res.params)))
    for i, name in enumerate(names):
        R[i, list(res.params.index).index(name)] = 1.0
    test = res.wald_test(R)
    return float(np.asarray(test.statistic).ravel()[0]), float(np.asarray(test.pvalue).ravel()[0])


def main() -> None:
    rates = pd.read_csv(RATES)
    panel = es.build_panel(rates)
    rows = []

    est, low, high = simple_did(panel)
    rows.append({"check": "main", "detail": "all states", "estimate": est, "ci_low": low, "ci_high": high})

    stat, p = pre_trend_test(panel)
    rows.append({"check": "pre_trend_joint_test", "detail": f"chi2={stat:.2f}, p={p:.3f}",
                 "estimate": np.nan, "ci_low": np.nan, "ci_high": np.nan})

    loo = []
    for state in sorted(panel["state"].unique()):
        est_s, low_s, high_s = simple_did(panel[panel["state"] != state])
        loo.append((state, est_s))
        rows.append({"check": "leave_one_state_out", "detail": f"drop {state}",
                     "estimate": est_s, "ci_low": low_s, "ci_high": high_s})

    placebo_panel = panel[panel["year"] <= 2013]
    est_p, low_p, high_p = simple_did(placebo_panel, post_year=2010)
    rows.append({"check": "placebo_2010", "detail": "fake expansion 2010, 2008-2013 data",
                 "estimate": est_p, "ci_low": low_p, "ci_high": high_p})

    est_nd, low_nd, high_nd = simple_did(panel[panel["state"] != "DC"])
    rows.append({"check": "drop_DC", "detail": "without DC",
                 "estimate": est_nd, "ci_low": low_nd, "ci_high": high_nd})

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print(out.round(4).to_string(index=False))
    lo, hi = min(loo, key=lambda t: t[1]), max(loo, key=lambda t: t[1])
    print(f"\nleave-one-out range: {lo[1]:.4f} (drop {lo[0]}) to {hi[1]:.4f} (drop {hi[0]})")


if __name__ == "__main__":
    main()
