# Validation notes

**Assessment: share with caveats.**

- The final code keeps the intended confounders: severity and age.
- Propensity and outcome predictions are cross-fitted.
- Each model owns its preprocessing state.
- The doubly robust AIPW formula is retained.
- The confidence interval uses a simple 200-replicate percentile bootstrap.
- `class_weight="balanced"` was removed because it distorted absolute mortality probabilities.

The final estimate is **+1.43 percentage points** with a bootstrap 95% CI of **−0.07 to +2.77**. The interval includes zero, and unmeasured operational confounding remains possible.
