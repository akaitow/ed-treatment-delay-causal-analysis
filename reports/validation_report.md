# Validation notes

**Assessment: share with caveats.**

- All 9,994 visits across severity levels 1-5 are included.
- Severity and age are adjustment variables, not eligibility filters.
- Propensity and outcome predictions are cross-fitted.
- The doubly robust AIPW formula and simple 200-replicate percentile bootstrap are retained.
- `class_weight="balanced"` is omitted because it distorts absolute mortality probabilities.
- The aggregate crude difference is -0.73 percentage points, while mortality is higher with high delay within every severity level.

The final estimate is **+2.15 percentage points** with a bootstrap 95% CI of **-0.36 to +6.61**. The interval includes zero. High-delay overlap is sparse at severity levels 4 and 5 (25 visits each), and unmeasured operational confounding remains possible.
