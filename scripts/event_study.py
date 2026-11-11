"""Difference-in-differences and event study: Medicaid expansion and uninsurance.

Groups (verify both lists against KFF or the CMS expansion tracker before results):
- Treated: states that expanded in 2014, plus DC.
- Comparison: states that had not expanded by the end of 2019.
- Excluded: states that expanded in 2015-2019 (their timing changes the treatment).
- Wisconsin is excluded throughout (2014 file unavailable).

Model: weighted least squares of the state-year uninsured rate on state and year
fixed effects, plus treated-by-year indicators. Weights are the state-year sample
population. Standard errors are clustered by state.

Outputs:
    data/output/event_study_coefficients.csv
    data/output/event_study.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

RATES = Path("data/interim/state_year_rates.csv")
OUT_DIR = Path("data/output")

TREATED = {
    "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "HI", "IL", "IA", "KY", "MD", "MA",
    "MI", "MN", "NV", "NH", "NJ", "NM", "NY", "ND", "OH", "OR", "RI", "VT", "WA", "WV",
}
COMPARISON = {
    "AL", "FL", "GA", "ID", "KS", "MS", "MO", "NE", "NC", "OK", "SC", "SD", "TN",
    "TX", "UT", "WY",
}
REFERENCE_YEAR = 2013
EXPANSION_YEAR = 2014


def build_panel(rates: pd.DataFrame) -> pd.DataFrame:
    panel = rates[rates["state"].isin(TREATED | COMPARISON)].copy()
    panel["treated"] = panel["state"].isin(TREATED).astype(float)
    panel["post"] = (panel["year"] >= EXPANSION_YEAR).astype(float)
    return panel.reset_index(drop=True)


def design_matrix(panel: pd.DataFrame, event_study: bool) -> pd.DataFrame:
    """State and year fixed effects, plus treatment terms."""
    state_fe = pd.get_dummies(panel["state"], prefix="state", drop_first=True, dtype=float)
    year_fe = pd.get_dummies(panel["year"], prefix="year", drop_first=True, dtype=float)
    X = pd.concat([state_fe, year_fe], axis=1)

    if event_study:
        for y in sorted(panel["year"].unique()):
            if y == REFERENCE_YEAR:
                continue
            X[f"treated_x_{y}"] = panel["treated"] * (panel["year"] == y).astype(float)
    else:
        X["treated_x_post"] = panel["treated"] * panel["post"]

    return sm.add_constant(X)


def fit(panel: pd.DataFrame, event_study: bool):
    X = design_matrix(panel, event_study)
    groups = panel["state"].astype("category").cat.codes
    model = sm.WLS(panel["uninsured_rate"], X, weights=panel["pop_sample"])
    return model.fit(cov_type="cluster", cov_kwds={"groups": groups})


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rates = pd.read_csv(RATES)
    panel = build_panel(rates)
    print(f"states: {panel['state'].nunique()} "
          f"(treated {panel.loc[panel['treated'] == 1, 'state'].nunique()}, "
          f"comparison {panel.loc[panel['treated'] == 0, 'state'].nunique()}); "
          f"state-years: {len(panel)}")

    simple = fit(panel, event_study=False)
    coef = simple.params["treated_x_post"]
    ci = simple.conf_int().loc["treated_x_post"]
    print(f"\nDiD (post-2014 effect on uninsured rate): {coef:.4f} "
          f"(95% CI {ci[0]:.4f} to {ci[1]:.4f}), p = {simple.pvalues['treated_x_post']:.4f}")

    es = fit(panel, event_study=True)
    rows = []
    for y in sorted(panel["year"].unique()):
        if y == REFERENCE_YEAR:
            rows.append({"year": int(y), "coef": 0.0, "ci_low": 0.0, "ci_high": 0.0})
            continue
        name = f"treated_x_{y}"
        low, high = es.conf_int().loc[name]
        rows.append({"year": int(y), "coef": es.params[name], "ci_low": low, "ci_high": high})
    coefs = pd.DataFrame(rows)
    coefs.to_csv(OUT_DIR / "event_study_coefficients.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(coefs["year"], coefs["coef"],
                yerr=[coefs["coef"] - coefs["ci_low"], coefs["ci_high"] - coefs["coef"]],
                fmt="o", capsize=3)
    ax.axhline(0, color="grey", lw=1)
    ax.axvline(EXPANSION_YEAR - 0.5, color="red", ls="--", lw=1)
    ax.set_xlabel("Year")
    ax.set_ylabel(f"Effect on uninsured rate (relative to {REFERENCE_YEAR})")
    ax.set_title("Medicaid expansion: event study, low-income adults 19-64")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "event_study.png", dpi=150)
    print(f"\nwrote {OUT_DIR / 'event_study_coefficients.csv'} and {OUT_DIR / 'event_study.png'}")


if __name__ == "__main__":
    main()
