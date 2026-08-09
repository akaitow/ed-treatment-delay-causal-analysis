# Methodology

## Question

Across severity levels 1-5, what is the mortality risk difference for treatment delay >=160 versus <160 minutes?

## Model

- Population: all 9,994 complete visits; no severity level is excluded
- Confounders: `Severity_Level` and `Dim_Patient.Age`
- Propensity model: logistic regression
- Outcome models: separate logistic regressions for high and lower delay
- Cross-fitting: five shuffled folds
- Estimator: augmented inverse probability weighting (AIPW)
- Confidence interval: 2.5th and 97.5th percentiles from 200 row-bootstrap estimates

The outcome models do not use `class_weight="balanced"` because AIPW needs population-risk probabilities rather than classification-oriented scores.

## AIPW

For each visit, the estimator combines an outcome-model prediction with an inverse-probability weighted residual. The high- and lower-delay risks are averaged separately; their difference is the reported effect.

AIPW is doubly robust: it can remain consistent if either the propensity model or the outcome model is correct, provided the other causal assumptions hold. This adjustment does not create true randomization.

## Assumptions

Consistency, positivity, no interference, correct time ordering, and no important unmeasured confounding. Positivity is weakest in severity levels 4 and 5, with only 25 high-delay visits in each. The 160-minute threshold is operational, not clinically validated.
