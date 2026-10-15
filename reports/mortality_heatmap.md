# Mortality heatmap with marginal mortality bars

The new chart is generated from the **same complete-case analysis cohort** used
in `analysis.py`. The raw workbook is intentionally not checked into Git.

Run from the repository root:

```bash
pip install -r requirements.txt
python plot_mortality_heatmap.py --input data/raw/mortality.xlsx
python -m unittest discover -s tests -v
```

Outputs (generated locally, not tracked): 
- `figures/04_mortality_heatmap_marginals.png` — 240 dpi image
- `figures/04_mortality_heatmap_marginals.svg` — editable vector graphic
- `figures/04_mortality_heatmap_marginals.pdf` — vector print export

**Axes and encoding:** severity 1–5 on the x-axis; treatment delay in minutes
on the y-axis, defaulting to <40, 40–<80, 80–<120, 120–<160, and ≥160;
observed percent mortality as a sequential color scale. The top bars show
mortality by severity pooled across delay; the right bars show mortality by delay
pooled across severity. Cell annotations include the cohort size (`n`).

Mortality rates are computed as **deaths divided by visits** in each category.
The marginal bars use pooled deaths divided by pooled visits, rather than an
unweighted average of heatmap tile rates. Missing groups are blank. Cells with
fewer than 30 visits carry a dagger (†) as a small-sample warning.

To change the delay bands while preserving 160 minutes as a boundary:

```bash
python plot_mortality_heatmap.py --input data/raw/mortality.xlsx --edges 20 40 60 80 100 120 140 160
```

This graphic displays **unadjusted observed mortality**, not age-adjusted or
AIPW causal effects. The project's original AIPW results remain unchanged.
