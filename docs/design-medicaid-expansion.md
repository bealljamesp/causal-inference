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
- **Income:** use the `POVPIP` column (income-to-poverty ratio in percent) directly, rather than computing it from household income.
- **Weights and standard errors:** use person weights for estimates and the ACS replicate weights for standard errors, since the ACS sampling design is not simple random sampling.

## Sample coverage

- The analysis covers the 50 states and DC, 2008 to 2019, except Wisconsin.
- Wisconsin is excluded because its 2014 ACS file could not be downloaded from the Census site. 2014 is the first post-expansion year, so this gap falls exactly where the estimate is measured. Excluding Wisconsin from every year keeps the panel balanced. The leave-one-out robustness check shows whether the estimate depends on it.
- All 600 state-years have replicate-weight standard errors. They range from about 0.004 to 0.037, with the largest in the smallest states (for example, SD and WY in 2008), where samples run 400 to 800 records.

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

## Results (provisional)

Status: estimates from the current pipeline. The treated and comparison lists are not yet verified against KFF or the CMS tracker, so treat these as provisional until that check is done.

**Sample.** 43 states: 27 treated (2014 expansion) and 16 comparison. ACS 1-year PUMS, 2008 to 2019 excluding 2020, Wisconsin excluded. Adults 19 to 64 with income-to-poverty ratio at or below 138%. The outcome is the weighted share of these adults with no coverage, so it runs from 0 to 1.

**Main estimate.** Weighted two-way fixed effects DiD, state-clustered standard errors:

- Coefficient on Treated x Post: −0.071, meaning a 7.1 percentage point drop in the uninsured share (95% CI −0.106 to −0.037; cluster-robust SE 0.0175, t = −4.06).
- Wild cluster bootstrap p-value: 0.0008 (Rademacher weights by state, B = 9,999). This is the primary inference, because 43 clusters is a modest number for asymptotic standard errors.
- Asymptotic normal p-value: 0.0001, reported for comparison.
- Replicate-weight SE: 0.0016. This captures ACS sampling noise only, not within-state correlation over time, so it is much smaller than the cluster SE and is not used for inference.

**Event study.** Pre-period coefficients (2008 to 2012, relative to 2013) are jointly indistinguishable from zero (Wald test p = 0.572). Post-2014 coefficients show the decline. The event-study coefficients have not yet been bootstrapped.

**Robustness.**

- Leave-one-state-out: estimates range from −0.058 to −0.080.
- Dropping DC: −0.072.
- Placebo expansion in 2010 (pre-2014 data only): −0.007 (95% CI −0.020 to 0.007).

## What would change the conclusion

- Pre-trends that diverge: the parallel-trends assumption is in doubt and the estimate should not be read causally.
- An estimate that is sensitive to dropping a single state: report it as fragile.
- A placebo estimate that is large: the design is picking up something other than the policy.

## Limitations

- Expansion was not random. States that expanded may differ in ways that also affect uninsurance trends, such as political composition and existing programs. Parallel trends is the assumption that handles this, and it is not testable directly.
- The ACS measures coverage at a point in time through self-report, which has known measurement error.
- Spillovers into non-expansion states (for example, from cross-border enrollment) would bias the estimate toward zero.
- The ACA Marketplace launched alongside expansion, so the estimate captures both policies, not Medicaid expansion alone.
- Inference depends on how many states are clustered. With 43 clusters, the bootstrap p-value is the more defensible number; the asymptotic p-value is about eight times smaller.
- Wisconsin is excluded because its 2014 file was unavailable. The leave-one-out check covers its absence only indirectly.

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
