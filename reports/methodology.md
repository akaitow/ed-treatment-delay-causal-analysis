# Methodology

## Research question and estimand

The target question is whether mortality risk would differ if otherwise comparable low-severity emergency-department visits experienced treatment delay at or above 160 minutes rather than below 160 minutes.

An RCT would be the strongest design for making treatment timing independent of prognosis, but deliberately imposing treatment delays may be unethical or infeasible. This analysis therefore emulates a defined intervention contrast using observational data. It does not reproduce randomization, and identification depends on consistency, conditional exchangeability, positivity, and correct temporal ordering.

The estimand is the average treatment effect on the risk-difference scale in the eligible population:

`E[Y(High delay) − Y(Lower delay)]`

where high delay means `Treatment_Delay_Minutes >= 160`, lower delay means `< 160`, and mortality is binary.

## Source and cohort

- Workbook sheets: `model` and `Fact_Patient_Visits`
- Analysis period represented in the source: 2024-01-01 through 2025-12-31
- Grain: one visit
- Eligibility: `Severity_Level` between 1 and 3 inclusive
- Required complete fields: exposure, outcome, patient ID, and listed baseline covariates
- Patient IDs are restored with a validated one-to-one merge on `Visit_ID` and are used for grouped cross-fitting and clustered uncertainty.

The cohort restriction is critical. The unfiltered sample mixes patients with very different severity profiles, creating a descriptive reversal between the full cohort and severity levels 1–3.

## Covariates

The adjustment set uses variables available at or plausibly before treatment delay:

- clinical need: severity level, diagnosis category, baseline risk category, comorbidities;
- patient characteristics: age, gender, insurance, ambulance arrival;
- setting: hospital, department, admission type;
- timing before treatment: triage delay.

Downstream fields—mortality, ICU requirement, length of stay, readmission, and the treatment delay itself—are excluded from the covariates. Doctor attributes are excluded because assignment timing relative to the exposure is not documented and they could sit on the operational pathway from setting to delay and outcome.

## Estimation

The analysis uses five-fold cross-fitted AIPW:

1. patients are assigned to folds with stratification on the high-delay indicator;
2. in each training fold, a propensity model predicts high delay;
3. separate outcome models predict mortality under high and lower delay;
4. all nuisance predictions for a visit come from models that did not train on that patient's fold;
5. the AIPW pseudo-outcomes are averaged to estimate adjusted risks and their difference.

The propensity and outcome models use median imputation and scaling for numeric fields, most-frequent imputation and one-hot encoding for categorical fields, and L2-regularized logistic regression. Outcome models do not use class weights because the target is a calibrated risk, not classification accuracy.

Estimated propensities are clipped to `[0.01, 0.99]` for numerical stability. The number clipped and the resulting weight distribution are reported rather than treated as invisible implementation details.

## Uncertainty

The standard error is calculated from the AIPW influence curve with one-way clustering by patient. The 95% confidence interval is the point estimate plus or minus 1.96 standard errors. This accounts for the small number of patients with repeated visits but does not address model or unmeasured-confounding uncertainty.

## Diagnostics

- Absolute standardized mean differences (SMDs) are computed for numeric fields and every categorical level before and after inverse-probability weighting.
- `|SMD| >= 0.10` is used as a conventional diagnostic flag, not a proof of exchangeability.
- Propensity minima and maxima, clipping count, 99th-percentile and maximum weights, and effective sample sizes are reported.
- The primary result is repeated with 120-, 160-, and 200-minute exposure thresholds.

## Identification assumptions

A causal interpretation requires:

1. consistency between the defined delay interventions and observed exposure;
2. conditional exchangeability after adjusting for the measured baseline covariates;
3. positivity for both exposure conditions throughout the covariate distribution;
4. no interference between visits;
5. correct temporal ordering and sufficient nuisance-model specification.

These assumptions cannot be fully verified from the workbook. In particular, congestion, staffing, calendar time, and other operational factors may affect both delay and mortality.

## Reporting framework

The repository's narrative follows the spirit of [STROBE](https://www.strobe-statement.org/): the design, setting, eligibility rules, variables, methods, results, and limitations are explicit. Causal assumptions follow the framework in Hernán and Robins' [*Causal Inference: What If*](https://www.hsph.harvard.edu/miguel-hernan/wp-content/uploads/sites/1268/2024/04/hernanrobins_WhatIf_26apr24.pdf). Balance diagnostics follow propensity-weighting guidance from [Austin and Stuart](https://pmc.ncbi.nlm.nih.gov/articles/PMC4626409/), and cross-fitting follows modern AIPW practice described by [Zhong et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC8796813/).
