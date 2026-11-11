"""Uninsured rate per state-year, with ACS replicate-weight standard errors.

Sample: adults aged 19-64 with POVPIP <= 138 (income-to-poverty ratio, percent).
Outcome: HICOV == 2 (no health insurance coverage).

For each state-year, the rate is computed with the main person weight (PWGTP) and
with each of the 80 replicate weights (PWGTP1-80). The ACS standard error is

    SE = sqrt( (4/80) * sum_r (theta_r - theta)^2 )

Output: data/interim/state_year_rates.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PART_DIR = Path("data/interim/pums_person")
OUT = Path("data/interim/state_year_rates.csv")
EXCLUDED = {"WI"}  # 2014 file unavailable; see design doc
REP = [f"PWGTP{i}" for i in range(1, 81)]


def rates_for_partition(path: Path) -> dict:
    df = pd.read_parquet(path)
    year = int(df["year"].iloc[0])
    state = str(df["state"].iloc[0])

    sample = df[df["AGEP"].between(19, 64) & (df["POVPIP"] <= 138) & df["HICOV"].notna()]
    if sample.empty:
        raise ValueError(f"{year} {state}: empty analysis sample")

    w_main = sample["PWGTP"].to_numpy(dtype=float)
    W = sample[REP].to_numpy(dtype=float)
    if np.isnan(W).any():
        raise ValueError(f"{year} {state}: replicate weights contain missing values")
    uninsured = (sample["HICOV"] == 2).to_numpy(dtype=float)

    theta = float((w_main * uninsured).sum() / w_main.sum())
    theta_r = (W * uninsured[:, None]).sum(axis=0) / W.sum(axis=0)
    se = float(np.sqrt((4.0 / 80.0) * np.sum((theta_r - theta) ** 2)))

    return {
        "state": state,
        "year": year,
        "uninsured_rate": theta,
        "se": se,
        "pop_sample": float(w_main.sum()),
        "n_records": len(sample),
    }


def main() -> None:
    rows = []
    for path in sorted(PART_DIR.glob("*.parquet")):
        year_str, state = path.stem.split("_")
        if state in EXCLUDED:
            continue
        rows.append(rates_for_partition(path))
        print(f"[ok] {year_str} {state}", flush=True)

    out = pd.DataFrame(rows).sort_values(["state", "year"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"[done] {len(out)} state-years written to {OUT}")


if __name__ == "__main__":
    main()
