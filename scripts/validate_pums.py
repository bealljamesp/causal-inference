"""Validate the national PUMS partitions and build a state-year summary.

Checks, per state-year:
- row count and weighted population total (sum of PWGTP), to compare with published totals
- share of missing values in POVPIP and HICOV
- values found in HICOV (expected: 1 and 2)
- sample size and weighted uninsured rate for adults 19-64 at or below 138% of poverty

Wisconsin is excluded from the analysis: its 2014 file could not be downloaded
(see docs/design-medicaid-expansion.md). The exclusion keeps the panel balanced.

Run from the repository root:
    python scripts/validate_pums.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from pull_acs_pums import STATES, YEARS  # noqa: E402

PART_DIR = Path("data/interim/pums_person")
OUT = Path("data/interim/validation_summary.csv")
EXCLUDED = {"WI": "2014 file unavailable from Census; see design doc"}
COLUMNS = ["year", "state", "AGEP", "HICOV", "POVPIP", "PWGTP", "has_replicate_weights"]


def summarize(df: pd.DataFrame) -> dict:
    total_weight = df["PWGTP"].sum()
    sample = df[df["AGEP"].between(19, 64) & (df["POVPIP"] <= 138)]
    sample_weight = sample["PWGTP"].sum()
    uninsured = sample.loc[sample["HICOV"] == 2, "PWGTP"].sum()
    return {
        "rows": len(df),
        "pop_weighted": total_weight,
        "missing_povpip_share": df["POVPIP"].isna().mean(),
        "missing_hicov_share": df["HICOV"].isna().mean(),
        "hicov_values": ",".join(str(int(v)) for v in sorted(df["HICOV"].dropna().unique())),
        "sample_rows": len(sample),
        "uninsured_rate_low_income": uninsured / sample_weight if sample_weight else float("nan"),
        "has_replicate_weights": bool(df["has_replicate_weights"].iloc[0]),
    }


def main() -> None:
    files = {(int(p.stem.split("_")[0]), p.stem.split("_")[1]): p for p in PART_DIR.glob("*.parquet")}

    expected = {(y, s) for y in YEARS for s in STATES if s not in EXCLUDED}
    missing = sorted(expected - set(files))
    extra = sorted(set(files) - expected - {(y, s) for y in YEARS for s in EXCLUDED})
    print(f"partitions found: {len(files)}; expected in analysis: {len(expected)}")
    print(f"missing from analysis: {missing or 'none'}")
    if extra:
        print(f"unexpected partitions: {extra}")

    rows = []
    for (year, state), path in sorted(files.items()):
        if state in EXCLUDED:
            continue
        df = pd.read_parquet(path, columns=COLUMNS)
        rows.append({"year": year, "state": state, **summarize(df)})

    summary = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT, index=False)
    print(f"wrote {len(summary)} state-years to {OUT}")

    # Quick look: Arizona (expanded 2014) and Texas (did not expand) over time
    view = summary[summary["state"].isin(["AZ", "TX"])]
    print("\nWeighted population total (sum of PWGTP):")
    print(view.pivot(index="year", columns="state", values="pop_weighted").round(0).to_string())
    print("\nUninsured rate, adults 19-64 at or below 138% of poverty:")
    print(view.pivot(index="year", columns="state", values="uninsured_rate_low_income").round(3).to_string())

    # Flags that need a look before analysis
    bad_hicov = summary[summary["hicov_values"] != "1,2"]
    if not bad_hicov.empty:
        print("\n[check] HICOV has unexpected values in:")
        print(bad_hicov[["year", "state", "hicov_values"]].to_string(index=False))
    no_replicates = summary.loc[~summary["has_replicate_weights"], ["year", "state"]]
    if not no_replicates.empty:
        print(f"\n[note] {len(no_replicates)} state-years without replicate weights (years: "
              f"{sorted(no_replicates['year'].unique())})")


if __name__ == "__main__":
    main()
