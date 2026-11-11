# Medicaid Expansion and Health Insurance Coverage

A difference-in-differences analysis of whether the 2014 ACA Medicaid expansion reduced uninsurance among low-income, working-age adults, using ACS 1-year microdata.

The research design, data rules, and limitations are in [docs/design-medicaid-expansion.md](docs/design-medicaid-expansion.md).

## Headline result (provisional)

Expansion states saw a 7.1 percentage point drop in the uninsured share among low-income adults, relative to non-expansion states (wild cluster bootstrap p = 0.0008). The treated and comparison state lists are still being verified against KFF and CMS. The design doc has the full results and robustness checks.

## Requirements

- Python 3.12
- pandas, pyarrow, numpy, statsmodels, scipy, matplotlib

## Running the analysis

Run from the repo root, in this order:

1. `python scripts/pull_acs_pums.py`: downloads ACS 1-year PUMS files for 2008 to 2019 and writes one Parquet partition per state-year to `data/interim/pums_person/`. Failed downloads are logged to `data/interim/pums_failures.csv`.
2. `python scripts/validate_pums.py`: checks partition counts and population totals.
3. `python scripts/state_year_rates.py`: computes weighted uninsured rates and replicate-weight standard errors for each state-year.
4. `python scripts/event_study.py`: DiD and event-study estimates with state-clustered standard errors.
5. `python scripts/robustness.py`: leave-one-state-out, placebo, and drop-DC checks.
6. `python scripts/replicate_se.py`: replicate-weight standard errors for the DiD and event-study terms.
7. `python scripts/wild_bootstrap.py`: wild cluster bootstrap p-value for the DiD term.

Outputs are written to `data/output/`. Raw downloads are not kept in the repo.
