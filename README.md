# Treatment delay and mortality in low-severity ED visits

An observational causal-inference project that asks a deceptively simple question:

> Among emergency-department visits with severity levels 1–3, how does mortality differ when treatment starts at least 160 minutes after triage rather than sooner?

![Crude mortality reverses after restricting to low-severity visits](figures/01_crude_mortality_reversal.png)

## The story in one minute

The full dataset appears to tell a reassuring story: mortality is lower in the high-delay group (2.67% versus 3.40%). That comparison is misleading because patients treated sooner are much more severely ill.

After restricting the question to 5,216 low-severity visits, the crude relationship reverses: mortality is 2.40% at or above 160 minutes versus 1.85% below 160 minutes. A cross-fitted augmented inverse probability weighted (AIPW) model estimates an adjusted risk difference of **+0.66 percentage points**, with a **95% confidence interval from −0.89 to +2.22 points**.

The point estimate is compatible with higher mortality under longer delay, but the interval also includes no effect and modest benefit. The evidence is therefore **hypothesis-generating, not conclusive**.

## Why this project matters

This is a practical example of Simpson's paradox and the limits of observational causal inference. When deliberately assigning harmful delays would make an RCT unethical or impractical, causal methods can emulate a clearly defined intervention contrast from observed data. They do not recreate randomization: the result remains conditional on measured confounding, overlap, consistency, and correct time ordering.

The most valuable result is not a dramatic causal claim; it is a transparent workflow that:

1. defines the low-severity cohort before modeling;
2. separates pre-treatment covariates from downstream outcomes;
3. uses propensity scores inside a doubly robust AIPW estimator;
4. cross-fits propensity and outcome models by patient;
5. reports balance, overlap, effective sample size, and extreme weights;
6. keeps uncertainty and unmeasured confounding visible.

## Main results

| Measure | Result |
|---|---:|
| Eligible visits / unique patients | 5,216 / 5,139 |
| High-delay visits / deaths | 998 / 24 |
| Lower-delay visits / deaths | 4,218 / 78 |
| Crude mortality risk difference | +0.56 percentage points |
| Adjusted AIPW risk difference | +0.66 percentage points |
| 95% confidence interval | −0.89 to +2.22 percentage points |
| Maximum absolute SMD, before / after weighting | 0.921 / 0.100 |
| Propensities clipped to [0.01, 0.99] | 14 |
| 99th percentile / maximum IPTW | 14.53 / 100.00 |

![Adjusted mortality risk difference](figures/03_effect_estimate.png)

## Method

- **Design:** observational visit-level cohort analysis covering 2024-01-01 through 2025-12-31.
- **Population:** severity levels 1–3 with complete exposure, outcome, patient ID, and baseline covariates.
- **Exposure:** treatment delay at or above 160 minutes versus below 160 minutes.
- **Outcome:** in-visit mortality flag.
- **Estimand:** average mortality risk difference in the eligible cohort.
- **Adjustment:** cross-fitted AIPW with regularized logistic nuisance models and five patient-grouped folds.
- **Uncertainty:** influence-curve standard error clustered by patient.
- **Diagnostics:** standardized mean differences, propensity range and clipping, inverse-probability weight distribution, and effective sample size.
- **Sensitivity:** the analysis is repeated at 120-, 160-, and 200-minute thresholds.

Start with the [storytelling notebook](notebooks/low_severity_delay_causal_analysis.ipynb) for the EDA, Simpson's paradox, RCT motivation, propensity scores, and doubly robust estimate. See [methodology.md](reports/methodology.md) for the full specification and [validation_report.md](reports/validation_report.md) for the quality review.

## Reproduce the analysis

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python analysis.py --input data/raw/mortality.xlsx
python -m unittest discover -s tests -v
```

The script rewrites the aggregate files in `results/`, the four figures in `figures/`, and [results.md](reports/results.md). It does not export row-level patient data.

## Repository map

```text
.
├── analysis.py                 # complete reproducible analysis
├── data/
│   ├── README.md               # data contract and publication safeguards
│   └── raw/                    # ignored by Git
├── figures/                    # publication-ready aggregate charts
├── notebooks/
│   └── low_severity_delay_causal_analysis.ipynb
├── reports/
│   ├── methodology.md          # estimand, models, assumptions, diagnostics
│   ├── results.md              # generated results snapshot
│   ├── validation_report.md    # issues fixed and remaining caveats
│   └── chart_map.md            # visual design and evidence map
├── results/                    # machine-readable aggregate outputs
└── tests/                      # deterministic utility tests
```

## Limitations

- The workbook's provenance, generation process, de-identification status, and public-use license have not been independently verified. Raw data are therefore excluded.
- The 160-minute threshold is an operational choice, not a validated clinical cutoff.
- Treatment timing is not randomized. AIPW only addresses measured confounding under its assumptions.
- Calendar time, staffing, crowding, and other operational factors are not fully measured in the model table.
- Some estimated propensities are near one, producing large weights and sensitivity to model specification.
- Mortality is rare in the eligible cohort (102 deaths), so confidence intervals are wide.
- Severity numbering is interpreted from the observed monotonic mortality pattern and project context; the source data dictionary should confirm that levels 1–3 are the intended low-severity group.

## References

- [STROBE reporting guidance for observational studies](https://www.strobe-statement.org/)
- Hernán MA, Robins JM. [*Causal Inference: What If*](https://www.hsph.harvard.edu/miguel-hernan/wp-content/uploads/sites/1268/2024/04/hernanrobins_WhatIf_26apr24.pdf)
- Austin PC, Stuart EA. [Moving towards best practice when using inverse probability of treatment weighting](https://pmc.ncbi.nlm.nih.gov/articles/PMC4626409/)
- Zhong Y, et al. [AIPW: augmented inverse probability-weighted estimation of average causal effects](https://pmc.ncbi.nlm.nih.gov/articles/PMC8796813/)

## Responsible use

This repository is an analytical portfolio project, not clinical guidance. Do not use its estimates for patient-care or operational decisions without validating the source data, clinical definitions, causal assumptions, and model specification with domain experts.
