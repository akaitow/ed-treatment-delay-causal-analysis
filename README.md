# ED treatment delay and mortality

## Executive summary

- **Signal:** after adjustment, high delay was associated with **+2.15 percentage points** mortality.
- **Uncertainty:** the bootstrap 95% CI was **-0.36 to +6.61 points**, so the result is not conclusive.
- **Decision:** reduce avoidable delays and study them prospectively; do not treat 160 minutes as a proven clinical cutoff.

## Situation

Emergency departments prioritize urgent patients. This project asks whether treatment beginning at or after 160 minutes may increase mortality across all severity levels.

## Complication

The pooled data look reassuring: mortality is 0.73 points lower in the high-delay group. But higher-severity patients are usually treated sooner and are more likely to die. Within every severity level, observed mortality is higher with high delay: a practical example of Simpson's paradox.

![Crude mortality by treatment delay within every severity level](figures/01_crude_mortality_reversal.png)

![Severity, mortality, and treatment timing](figures/02_severity_mechanism.png)

## Question

> Across severity levels 1-5, how would mortality differ if treatment began at or after 160 minutes rather than sooner?

## Evidence

All 9,994 visits remain in the analysis. Age and severity are used for adjustment, not cohort exclusion. A propensity model estimates high-delay probability; separate mortality models estimate risk under high and lower delay. AIPW combines both parts, making the estimator doubly robust under the causal assumptions.

| Result | Estimate |
|---|---:|
| Adjusted mortality, high delay | 5.37% |
| Adjusted mortality, lower delay | 3.22% |
| AIPW risk difference | **+2.15 pp** |
| Bootstrap 95% CI | **-0.36 to +6.61 pp** |

![Doubly robust mortality estimate](figures/03_effect_estimate.png)

## Answer

Long delay may increase mortality across ED severity levels, but the interval includes no effect. Treat this as an operational warning, not proof of a causal threshold.

1. Monitor median and 90th-percentile delay by severity and week.
2. Investigate staffing, queue, room, and handoff bottlenecks.
3. Add crowding and staffing measures, then evaluate a prospective process improvement.

## Method

- **Cohort:** 9,994 visits across severity levels 1-5
- **Exposure:** treatment delay >=160 versus <160 minutes
- **Outcome:** in-visit mortality
- **Confounders:** severity and age
- **Estimator:** five-fold cross-fitted propensity-score AIPW
- **Uncertainty:** simple 200-replicate percentile bootstrap

AIPW adjusts measured confounding; it does not create true randomization. High-delay overlap is limited in severity levels 4 and 5 (25 visits each), and unmeasured operational confounding may remain.

## Run it

```bash
pip install -r requirements.txt
python analysis.py --input data/raw/mortality.xlsx
python -m unittest discover -s tests -v
```

See the [notebook](notebooks/ed_delay_causal_analysis.ipynb), [methodology](reports/methodology.md), and [validation notes](reports/validation_report.md).

> Portfolio analysis only - not clinical guidance.
