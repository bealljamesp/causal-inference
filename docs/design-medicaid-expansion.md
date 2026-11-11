# Design: Medicaid Expansion and Health Insurance Coverage (DRAFT)

Status: draft for review. Nothing here is implemented yet.

## Research question

Did the 2014 Medicaid expansion under the ACA reduce uninsurance among low-income, working-age adults in expansion states relative to non-expansion states?

## Why this design

Expansion was a state-level decision. Some states adopted it in 2014 and others did not, which gives a difference-in-differences (DiD) design: compare the change in uninsurance before and after 2014 in expansion states with the same change in non-expansion states. The identifying assumption is parallel trends: absent expansion, the two groups would have followed similar paths.

## Treatment and comparison

- **Treated:** states that expanded Medicaid in 2014. The exact list must be verified against an official source (KFF or the CMS Medicaid expansion tracker) before any analysis. Record the source and date in the code.
- **Comparison:** states that had not expanded by the end of the sample window.
- **Excluded from the main analysis:** states that expanded in later years (for example, 2015 or after). They are a useful robustness check, not part of the main estimate, because their timing changes the treatment definition.

## Data

- **Source:** American Community Survey (ACS) 1-year Public Use Microdata Sample (PUMS), 2008 to 2019, excluding 2020 (experimental release and collection disruption).
- **Why 1-year PUMS and not 5-year:** 5-year files pool overlapping years, so adjacent periods share respondents. That breaks the independence DiD relies on. Individual-level microdata also let us restrict to the target population.
- **Sample:** adults aged 19 to 64, with household income at or below 138% of the federal poverty line (the Medicaid expansion threshold). Income-to-poverty ratios are computed from household income and household size.
- **Weights and standard errors:** use person weights for estimates and the ACS replicate weights for standard errors, since the ACS sampling design is not simple random sampling.

## Outcome

- Primary: indicator for having no health insurance coverage.
- Secondary (if time): Medicaid coverage specifically, and employment status, to check for labor-market responses.

## Specification

Two-way fixed effects DiD on the state-year panel, with state and year fixed effects:

    y_st = alpha_s + gamma_t + beta * (Treated_s x Post_t) + X_st * delta + e_st

- y_st: share of low-income adults uninsured in state s, year t (weighted).
- Post_t: indicator for years 2014 onward. Use 2014 as the first post year, since most coverage gains began in 2014.
- beta: the average effect on the treated states. The headline number is the coefficient on the interaction.

Given the staggered-adoption concern, the main model uses only the 2014 expansion states and never-expanders. This avoids the known problems with two-way fixed effects when treatment timing differs across groups.

## Event study and parallel trends

Replace Post_t with event-time indicators (years relative to 2014) and plot the coefficients. The pre-period coefficients should be close to zero and statistically indistinguishable from it. This is the main check on the identifying assumption. Report the plot and the pre-trend test. Do not describe the design as "proving" parallel trends; it can only fail to reject them.

## Robustness checks

1. Drop one treated or comparison state at a time (leave-one-out).
2. Vary the sample window (for example, 2010 to 2017 only) to check sensitivity to the start and end years.
3. Placebo test: assign a fake expansion year (for example, 2010) and confirm the estimate is near zero.
4. Vary the income cutoff (for example, 100% and 200% of the poverty line).

## What would change the conclusion

- Pre-trends that diverge: the parallel-trends assumption is in doubt and the estimate should not be read causally.
- An estimate that is sensitive to dropping a single state: report it as fragile.
- A placebo estimate that is large: the design is picking up something other than the policy.

## Limitations

- Expansion was not random. States that expanded may differ in ways that also affect uninsurance trends, such as political composition and existing programs. Parallel trends is the assumption that handles this, and it is not testable directly.
- The ACS measures coverage at a point in time through self-report, which has known measurement error.
- Spillovers into non-expansion states (for example, from cross-border enrollment) would bias the estimate toward zero.
- The ACA Marketplace launched alongside expansion, so the estimate captures both policies, not Medicaid expansion alone.

## Deliverables

1. Data pull script with the ACS PUMS download and a documented, versioned cache.
2. Cleaned state-year panel with the sample rules applied.
3. DiD and event-study estimates with replicate-weight standard errors.
4. Robustness table and event-study figure.
5. A short write-up (two pages) with the result, the assumption, and the limitations.

## Open questions

- Confirm the 2014 expansion state list and its source.
- Decide whether to use the Census Bureau's `pums` helper or a direct download of the microdata files.
- Decide whether the first deliverable is the state-level panel (faster) or the full microdata model (stronger, more work).
