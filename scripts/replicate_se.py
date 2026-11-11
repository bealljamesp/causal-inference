"""Replicate-weight standard errors for the difference-in-differences estimates.

The WLS coefficients are linear in the state-year rates, so each coefficient can be
re-estimated with the rates from one replicate weight in place of the main rates.
The ACS replicate formula then gives a standard error that reflects sampling error
in the rates:

    SE_rep = sqrt( (4/80) * sum_r (beta_r - beta)^2 )

Weights stay fixed at each state-year's main sample population. This SE is compared
with the state-clustered SE from event_study.py; they capture different sources of
uncertainty, so the larger one is the conservative choice.

Outputs:
    data/interim/state_year_replicates.csv   replicate rates, one row per state-year
    data/output/replicate_se.csv             estimates with both SEs
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

import event_study as es
import state_year_rates as syr

REP_OUT = Path("data/interim/state_year_replicates.csv")
OUT = Path("data/output/replicate_se.csv")
REP_COLS = [f"r{i}" for i in range(1, 81)]


def replicate_rates(path: Path) -> dict:
    df = pd.read_parquet(path)
    year = int(df["year"].iloc[0])
    state = str(df["state"].iloc[0])
    sample = df[df["AGEP"].between(19, 64) & (df["POVPIP"] <= 138) & df["HICOV"].notna()]
    W = sample[syr.REP].to_numpy(dtype=float)
    if np.isnan(W).any():
        raise ValueError(f"{year} {state}: replicate weights contain missing values")
    u = (sample["HICOV"] == 2).to_numpy(dtype=float)
    rates = (W * u[:, None]).sum(axis=0) / W.sum(axis=0)
    return {"state": state, "year": year, **dict(zip(REP_COLS, rates))}


def load_replicate_rates() -> pd.DataFrame:
    if REP_OUT.exists():
        return pd.read_csv(REP_OUT)
    rows = [replicate_rates(p) for p in sorted(syr.PART_DIR.glob("*.parquet"))
            if p.stem.split("_")[1] not in syr.EXCLUDED]
    reps = pd.DataFrame(rows)
    REP_OUT.parent.mkdir(parents=True, exist_ok=True)
    reps.to_csv(REP_OUT, index=False)
    return reps


def fit_params(panel: pd.DataFrame, y: np.ndarray, event_study: bool) -> pd.Series:
    X = es.design_matrix(panel, event_study)
    res = sm.WLS(y, X, weights=panel["pop_sample"].to_numpy()).fit()
    return res.params


def main() -> None:
    rates = pd.read_csv(es.RATES)
    panel = es.build_panel(rates)
    reps = load_replicate_rates()
    aligned = panel[["state", "year"]].merge(reps, on=["state", "year"], how="left")
    if aligned[REP_COLS].isna().any().any():
        raise ValueError("replicate rates missing for some state-years in the panel")
    rep_matrix = aligned[REP_COLS].to_numpy(dtype=float)  # (state-years, 80)

    out_rows = []
    for event_study, label in [(False, "did"), (True, "event")]:
        main_params = fit_params(panel, panel["uninsured_rate"].to_numpy(), event_study)
        rep_params = np.vstack([
            fit_params(panel, rep_matrix[:, r], event_study).to_numpy() for r in range(80)
        ])  # (80, n_params)
        se_rep = np.sqrt((4.0 / 80.0) * np.sum((rep_params - main_params.to_numpy()) ** 2, axis=0))

        cluster = es.fit(panel, event_study=event_study)
        for i, name in enumerate(main_params.index):
            if name == "const" or name.startswith(("state_", "year_")):
                continue
            if label == "event" and name.startswith("treated_x_") and name.endswith("2013"):
                continue
            out_rows.append({
                "model": label,
                "term": name,
                "estimate": main_params[name],
                "se_replicate": se_rep[i],
                "se_cluster_state": cluster.bse[name],
            })

    out = pd.DataFrame(out_rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(out.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
