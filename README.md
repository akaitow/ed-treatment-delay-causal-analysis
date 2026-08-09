# Treatment delay and mortality in low-severity ED visits

## Executive Summary

- **Signal:** high delay was associated with **+1.43 percentage points** mortality after adjustment.
- **Uncertainty:** the bootstrap 95% CI was **−0.07 to +2.77 points**, so the result is not conclusive.
- **Decision:** reduce avoidable delays and study them prospectively; do not treat 160 minutes as a proven clinical cutoff.

## Situation

Emergency departments must prioritize urgent patients. This project asks whether long waits may create risk among visits already classified as low severity.

## Complication

The full sample looks reassuring: mortality is lower with high delay. That average is misleading because sicker patients are treated sooner and die more often. Among severity levels 1–3, the crude direction reverses.

![Crude mortality by treatment delay](figures/01_crude_mortality_reversal.png)

Severity affects both treatment timing and mortality—a practical example of Simpson's paradox.

![Severity, mortality, and treatment timing](figures/02_severity_mechanism.png)

## Question

> Among comparable severity 1–3 visits, how would mortality differ if treatment began at or after 160 minutes rather than sooner?

## Evidence

The analysis uses age and severity as the confounders. A propensity model estimates who receives high delay; separate mortality models estimate risk under high and lower delay. AIPW combines both parts, making the estimator doubly robust under the causal assumptions.

| Result | Estimate |
|---|---:|
| Adjusted mortality, high delay | 3.21% |
| Adjusted mortality, lower delay | 1.79% |
| AIPW risk difference | **+1.43 pp** |
| Bootstrap 95% CI | **−0.07 to +2.77 pp** |

![Doubly robust mortality estimate](figures/03_effect_estimate.png)

## Answer

Long delay may increase mortality in low-severity visits, but this dataset does not prove a causal threshold.

1. Monitor median and 90th-percentile delay by severity and week.
2. Investigate staffing, queue, room, and handoff bottlenecks.
3. Add crowding and staffing measures, then evaluate a prospective process improvement.

## Method

- **Cohort:** 5,216 visits at severity levels 1–3
- **Exposure:** treatment delay ≥160 versus <160 minutes
- **Outcome:** in-visit mortality
- **Confounders:** severity and age
- **Estimator:** five-fold cross-fitted propensity-score AIPW
- **Uncertainty:** simple 200-replicate percentile bootstrap

The raw workbook is excluded from Git. The analysis is observational and depends on consistency, positivity, correct time ordering, and no important unmeasured confounding.

## Run it

```bash
pip install -r requirements.txt
python analysis.py --input data/raw/mortality.xlsx
python -m unittest discover -s tests -v
```

See the [notebook](notebooks/low_severity_delay_causal_analysis.ipynb), [methodology](reports/methodology.md), and [validation notes](reports/validation_report.md).

> Portfolio analysis only—not clinical guidance.
