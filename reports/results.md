# Results snapshot

## Headline

In 5,216 low-severity visits (severity levels 1–3), mortality was 2.40% among visits with treatment delay at or above 160 minutes and 1.85% among visits below the threshold. After adjustment with cross-fitted AIPW, the estimated risk difference was +0.66 percentage points (95% CI -0.89 to +2.22).

This is an observational estimate, not proof that changing delay would cause the estimated change in mortality. The causal interpretation additionally requires consistency, positivity, no interference, correct time ordering, and no unmeasured confounding.

## Cohort and data

- Source: `mortality.xlsx`, sheets `model` and `Fact_Patient_Visits`
- Source date range: 2024-01-01 03:10:00 to 2025-12-31 21:58:00
- Analysis grain: one emergency-department visit
- Eligible cohort: severity levels 1–3 with complete required fields
- Visits: 5,216; unique patients: 5,139
- High-delay visits: 998 (24 deaths)
- Lower-delay visits: 4,218 (78 deaths)

## Diagnostics

- Maximum absolute SMD: 0.921 before weighting; 0.100 after weighting
- Features with |SMD| ≥ 0.10: 8 before; 1 after
- Raw propensity range: 0.011–1.000
- Propensities clipped to [0.01, 0.99]: 14
- 99th percentile / maximum IPTW: 14.53 / 100.00
- Effective sample size: 497 high-delay; 1349 lower-delay

## Interpretation

The descriptive reversal between the full sample and the low-severity cohort is consistent with confounding by severity. The adjusted analysis estimates the average risk difference under the measured-covariate model. Treat the estimate as hypothesis-generating because the delay threshold is operational rather than clinically validated, the outcome is rare, calendar-time and congestion measures are incomplete, and unmeasured confounding remains possible.
