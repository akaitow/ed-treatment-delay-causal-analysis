# Validation report

## Overall assessment: Share with caveats

The revised project is suitable for a portfolio and for methodological discussion. It is not ready to support clinical or operational decisions because data provenance is unverified, the exposure threshold is not clinically validated, overlap is imperfect, and unmeasured confounding remains plausible.

## Question and source

- Question: mortality risk difference for treatment delay at or above 160 minutes versus below 160 minutes among severity levels 1–3.
- Source: `mortality.xlsx`, sheets `model` and `Fact_Patient_Visits`.
- Source period: 2024-01-01 through 2025-12-31.
- Grain: one visit.

## Methodology review

The revised analysis now matches the project title by restricting to severity levels 1–3. Exposure coding is consistent (`>= 160` throughout), the estimand is explicit, only baseline or plausibly pre-treatment fields are adjusted, nuisance models are cross-fitted, class weighting is removed from risk models, and uncertainty is clustered by patient.

## Issues found and disposition

1. **High — cohort mismatch: fixed.** The original analysis used all severities despite a low-severity project title. The revised cohort is severity levels 1–3.
2. **High — unsupported causal wording: fixed.** The narrative now distinguishes descriptive reversal, adjusted association, identification assumptions, and residual uncertainty.
3. **High — outcome risk modeling: fixed.** The original outcome models used `class_weight="balanced"`, which targets classification behavior rather than calibrated population risk. The revised models use regularized logistic probabilities without class weighting.
4. **High — weak adjustment set: improved, not eliminated.** The original model adjusted only for severity and age. The revised set adds patient, clinical, operational-setting, and pre-treatment timing variables. Unmeasured operational confounding remains.
5. **Medium — inconsistent exposure definition: fixed.** Original charts used `> 160`; the model used `>= 160`. The repository consistently uses `>= 160`.
6. **Medium — balance plot did not measure balance: fixed.** The original severity plot was not a standardized balance diagnostic. The revised project reports SMDs before and after weighting.
7. **Medium — incomplete cross-fitting: fixed.** The original propensity model was cross-validated, but outcome predictions were in-sample. All nuisance predictions are now out of fold and patient-grouped.
8. **Medium — bootstrap description mismatch: fixed.** The original text called the estimate overlap-weighted while calculating standard IPTW/AIPW. The revised method names the ATE estimator correctly and uses a clustered influence-curve interval.
9. **Medium — positivity risk: remains.** Fourteen primary-analysis propensities are clipped; the maximum weight is 100 and the weighted effective sample size falls materially below the row count.
10. **Medium — source governance: remains.** Provenance, licensing, synthetic status, and de-identification have not been verified. The raw workbook is excluded from Git.

## Calculation spot-checks

- Model grain: **verified** — 9,994 rows and 9,994 unique `Visit_ID` values.
- Required-field completeness: **verified** — zero nulls across the modeled exposure, outcome, and selected covariates.
- Patient join: **verified** — model visits map one-to-one to the fact sheet and recover 9,738 patients overall.
- Low-severity cohort: **verified** — 5,216 visits and 5,139 unique patients.
- Crude risk, high delay: **verified** — 24 / 998 = 2.40%.
- Crude risk, lower delay: **verified** — 78 / 4,218 = 1.85%.
- Primary adjusted difference: **recomputed** — +0.66 percentage points; 95% CI −0.89 to +2.22.
- Measured balance: **verified** — maximum absolute SMD falls from 0.921 to 0.100; one encoded feature remains at or just above 0.10.

## Visualization review

- Bars begin at zero and show exact mortality rates.
- The reversal chart separates the full sample from the prespecified low-severity cohort.
- The balance plot uses a visible 0.10 reference line and shows before/after values without a redundant color legend.
- Effect and sensitivity plots include a zero reference and 95% intervals.
- Titles are descriptive; cohort, threshold, and uncertainty context appear in subtitles.

## Required caveats

- Observational adjustment does not prove causality.
- The 160-minute threshold is operational and should be clinically justified before substantive use.
- Near-positivity violations and large weights make the estimate specification-sensitive.
- Only 102 deaths occur in the eligible cohort; uncertainty is substantial.
- Unmeasured crowding, staffing, temporal, and care-pathway factors may bias the estimate.
- Confirm the source data dictionary's severity direction and the workbook's provenance before publication.

## Recommended next study improvements

1. Pre-register the cohort, threshold, estimand, covariate set, and sensitivity analyses.
2. Add arrival hour/day, occupancy, staffing, crowding, and queue measures collected before treatment.
3. Confirm severity coding and model a clinically meaningful delay intervention rather than relying on one cutoff.
4. Compare AIPW with overlap weighting or targeted maximum likelihood under a prespecified analysis plan.
5. Use negative controls or quantitative bias analysis to probe unmeasured confounding.
6. Obtain clinical and data-governance review before external substantive claims.

