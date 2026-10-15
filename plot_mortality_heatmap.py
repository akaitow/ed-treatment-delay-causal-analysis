"""Publication-ready heatmap of observed ED mortality with marginal risk bars.

The source workbook is intentionally kept outside the public repository. Run with:

    python plot_mortality_heatmap.py --input data/raw/mortality.xlsx

The script uses analysis.load_data so the cohort matches the repository's existing
complete-case analysis. All percentages are *observed*, not AIPW-adjusted risks.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SEVERITY_LEVELS = (1, 2, 3, 4, 5)
DEFAULT_DELAY_EDGES = (40, 80, 120, 160)

# Quiet, warm sequential color palette. Darker cells represent higher mortality.
PAPER = "#FCFCFA"
INK = "#24313A"
MUTED = "#71808A"
ACCENT = "#344D53"
PALE = "#E8ECE8"
HEAT_COLORS = ("#F5F6F2", "#EADDD2", "#DBBAA7", "#C88873", "#A94F49", "#6F2B35")


@dataclass(frozen=True)
class MortalityMatrix:
    """Cell counts and pooled (not unweighted cell-average) mortality rates."""

    visits: pd.DataFrame
    deaths: pd.DataFrame
    percentages: pd.DataFrame
    severity_percentages: pd.Series
    delay_percentages: pd.Series
    total_visits: int
    total_deaths: int


def _delay_labels(edges: Sequence[int]) -> list[str]:
    return [f"< {edges[0]}"] + [
        f"{left}–<{right}" for left, right in zip(edges[:-1], edges[1:])
    ] + [f"≥ {edges[-1]}"]


def make_mortality_matrix(
    frame: pd.DataFrame,
    delay_edges: Sequence[int] = DEFAULT_DELAY_EDGES,
) -> MortalityMatrix:
    """Aggregate ED visits, deaths and observed risks with explicit denominators.

    The last delay bin is open-ended. Boundary observations go into the bin to
    their right: 160 minutes is included in the '≥160' cohort, for example.
    Empty cells remain missing, rather than misleadingly displaying 0% deaths.
    """
    edges = tuple(delay_edges)
    if not edges or any(not isinstance(v, (int, np.integer)) for v in edges):
        raise ValueError("Delay edges must be a nonempty sequence of integer minutes.")
    if any(a >= b for a, b in zip((0, *edges[:-1]), edges)):
        raise ValueError("Delay edges must be positive, strictly increasing minutes.")

    columns = ("Severity_Level", "Treatment_Delay_Minutes", "Mortality_Flag")
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing source columns: {', '.join(missing)}")

    data = frame.loc[:, columns].copy()
    if data.isna().any().any():
        raise ValueError("Use complete-case data from analysis.load_data before plotting.")
    for name in columns:
        data[name] = pd.to_numeric(data[name], errors="raise")
    if not data["Severity_Level"].isin(SEVERITY_LEVELS).all():
        raise ValueError("Severity_Level must contain only levels 1–5.")
    if not data["Mortality_Flag"].isin((0, 1)).all():
        raise ValueError("Mortality_Flag must be encoded as 0 or 1.")
    if not np.isfinite(data["Treatment_Delay_Minutes"]).all():
        raise ValueError("Treatment_Delay_Minutes must be finite.")
    if (data["Treatment_Delay_Minutes"] < 0).any():
        raise ValueError("Treatment_Delay_Minutes cannot be negative.")
    if data.empty:
        raise ValueError("No visits available to plot.")

    labels = _delay_labels(edges)
    data["delay_bin"] = pd.cut(
        data["Treatment_Delay_Minutes"],
        bins=[0, *edges, np.inf],
        labels=labels,
        right=False,
        include_lowest=True,
    )

    # The groupby counts are the source of truth for both the cells and margins.
    groups = data.groupby(["delay_bin", "Severity_Level"], observed=False)["Mortality_Flag"]
    visits = groups.size().unstack().reindex(index=labels, columns=SEVERITY_LEVELS, fill_value=0).astype(int)
    deaths = groups.sum().unstack().reindex(index=labels, columns=SEVERITY_LEVELS, fill_value=0).astype(int)
    percentages = deaths.div(visits.where(visits.ne(0))).mul(100)
    severity_pct = deaths.sum(axis=0).div(visits.sum(axis=0).replace(0, np.nan)).mul(100)
    delay_pct = deaths.sum(axis=1).div(visits.sum(axis=1).replace(0, np.nan)).mul(100)

    assert int(visits.to_numpy().sum()) == len(data)
    assert int(deaths.to_numpy().sum()) == int(data["Mortality_Flag"].sum())
    return MortalityMatrix(
        visits=visits,
        deaths=deaths,
        percentages=percentages,
        severity_percentages=severity_pct,
        delay_percentages=delay_pct,
        total_visits=int(visits.to_numpy().sum()),
        total_deaths=int(deaths.to_numpy().sum()),
    )


def draw_mortality_heatmap(
    summary: MortalityMatrix,
    *,
    sparse_n: int = 30,
    dpi: int = 240,
) -> plt.Figure:
    """Create an editorial-style heatmap with aligned top/right marginal bars."""
    if sparse_n < 1:
        raise ValueError("sparse_n must be at least 1.")
    if dpi <= 0:
        raise ValueError("dpi must be positive.")

    nrows, ncols = summary.visits.shape
    rates = summary.percentages.to_numpy(dtype=float)
    counts = summary.visits.to_numpy(dtype=int)
    valid_rates = rates[np.isfinite(rates)]
    vmax = max(1.0, float(np.ceil(np.max(valid_rates) / 2) * 2)) if valid_rates.size else 1.0
    cmap = LinearSegmentedColormap.from_list("mortality_rust", HEAT_COLORS, N=256)
    cmap.set_bad(PALE)
    norm = Normalize(vmin=0, vmax=vmax)

    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none", "pdf.fonttype": 42})
    fig = plt.figure(figsize=(13.2, 8.8), facecolor=PAPER)
    gs = fig.add_gridspec(
        2, 3,
        left=0.12, right=0.935, bottom=0.195, top=0.785,
        width_ratios=(6.3, 2.55, 0.22),
        height_ratios=(1.52, 5.0),
        wspace=0.20, hspace=0.15,
    )
    ax_top = fig.add_subplot(gs[0, 0])
    ax_heat = fig.add_subplot(gs[1, 0])
    ax_side = fig.add_subplot(gs[1, 1], sharey=ax_heat)
    ax_cbar = fig.add_subplot(gs[1, 2])

    fig.text(0.12, 0.949, "MORTALITY  /  EMERGENCY CARE", color=ACCENT,
             fontsize=9.3, fontweight="bold", ha="left", va="top")
    fig.text(0.12, 0.906, "Mortality by severity and treatment delay", color=INK,
             fontsize=21, fontweight="bold", ha="left", va="top")
    fig.text(0.12, 0.855,
             f"Observed mortality  ·  {summary.total_visits:,} visits  ·  "
             f"{summary.total_deaths:,} deaths  ·  color shows percent of visits",
             color=MUTED, fontsize=10.8, ha="left", va="top")

    bar_margin = pd.concat((summary.severity_percentages, summary.delay_percentages))
    bar_max = max(1.0, float(bar_margin.max(skipna=True))) * 1.35
    xs = np.arange(ncols) + 0.5
    ys = np.arange(nrows) + 0.5

    # Top marginal: pooled mortality across all delay intervals, by severity.
    s_rates = summary.severity_percentages.to_numpy(dtype=float)
    ax_top.bar(xs, np.nan_to_num(s_rates), width=0.48, color=ACCENT, alpha=0.96)
    for x, val in zip(xs, s_rates):
        if np.isfinite(val):
            ax_top.text(x, val + bar_max * 0.045, f"{val:.1f}%", ha="center", va="bottom",
                        fontsize=9.7, color=INK, fontweight="bold")
    ax_top.set(xlim=(0, ncols), ylim=(0, bar_max))
    ax_top.set_xticks([])
    ax_top.set_yticks([])
    for spine in ax_top.spines.values():
        spine.set_visible(False)
    ax_top.axhline(0, color="#CBD2CF", linewidth=0.9)
    ax_top.text(0, 1.08, "BY SEVERITY  ·  POOLED MORTALITY", transform=ax_top.transAxes,
                ha="left", va="bottom", fontsize=9.2, fontweight="bold", color=MUTED)

    # Central heatmap. Each tile is a separately computed deaths/visits percentage.
    mesh = ax_heat.pcolormesh(
        np.arange(ncols + 1), np.arange(nrows + 1), np.ma.masked_invalid(rates),
        cmap=cmap, norm=norm, edgecolors=PAPER, linewidth=2.9, antialiased=True,
    )
    ax_heat.set(xlim=(0, ncols), ylim=(nrows, 0))
    ax_heat.set_xticks(xs, [str(s) for s in summary.visits.columns])
    ax_heat.set_yticks(ys, list(summary.visits.index))
    ax_heat.set_xlabel("Severity level", fontsize=11.5, color=INK, labelpad=14)
    ax_heat.set_ylabel("Treatment delay (minutes)", fontsize=11.5, color=INK, labelpad=18)
    ax_heat.tick_params(axis="both", length=0, pad=10, labelsize=11, colors=INK)
    for spine in ax_heat.spines.values():
        spine.set_visible(False)

    for row in range(nrows):
        for col in range(ncols):
            value, n = rates[row, col], counts[row, col]
            if not np.isfinite(value):
                ax_heat.text(col + 0.5, row + 0.52, "—", ha="center", va="center",
                             fontsize=13, color=MUTED)
                continue
            r, g, b, _ = cmap(norm(value))
            # Text contrast checked against the actual fill at each tile.
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            on_dark = luminance < 0.58
            fg = "#FFFFFF" if on_dark else INK
            sub = "#F0DBD9" if on_dark else MUTED
            marker = "†" if n < sparse_n else ""
            ax_heat.text(col + 0.5, row + 0.41, f"{value:.1f}%{marker}",
                         ha="center", va="center", fontsize=12.3,
                         fontweight="bold", color=fg)
            ax_heat.text(col + 0.5, row + 0.67, f"n={n:,}",
                         ha="center", va="center", fontsize=8.4, color=sub)

    # Right marginal: pooled mortality across severity levels, by delay band.
    d_rates = summary.delay_percentages.to_numpy(dtype=float)
    ax_side.barh(ys, np.nan_to_num(d_rates), height=0.49, color=ACCENT, alpha=0.96)
    for y, val in zip(ys, d_rates):
        if np.isfinite(val):
            ax_side.text(val + bar_max * 0.04, y, f"{val:.1f}%",
                         ha="left", va="center", fontsize=9.7,
                         fontweight="bold", color=INK)
    ax_side.set(xlim=(0, bar_max), ylim=(nrows, 0))
    ax_side.tick_params(axis="both", bottom=False, left=False, labelbottom=False, labelleft=False)
    for spine in ax_side.spines.values():
        spine.set_visible(False)
    ax_side.axvline(0, color="#CBD2CF", linewidth=0.9)
    ax_side.set_facecolor(PAPER)
    ax_side.text(0, 1.035, "BY DELAY  ·  POOLED MORTALITY", transform=ax_side.transAxes,
                 ha="left", va="bottom", fontsize=9.2, fontweight="bold", color=MUTED)

    cbar = fig.colorbar(mesh, cax=ax_cbar, orientation="vertical")
    cbar.outline.set_visible(False)
    cbar.locator = MaxNLocator(nbins=5)
    cbar.formatter = FuncFormatter(lambda value, _: f"{value:g}%")
    cbar.update_ticks()
    cbar.ax.tick_params(labelsize=8.3, length=0, colors=MUTED, pad=4)
    ax_cbar.text(0.5, 1.035, "RATE", transform=ax_cbar.transAxes,
                 ha="center", va="bottom", fontsize=9.2, fontweight="bold", color=MUTED)

    fig.text(0.12, 0.127,
             "Each tile = deaths ÷ visits in that severity × delay group.  "
             "Bars = pooled mortality (deaths ÷ visits), not mean tile percentages.",
             fontsize=9.5, color=INK, ha="left", va="top")
    fig.text(0.12, 0.099,
             f"† Fewer than {sparse_n} visits: interpret cautiously.  "
             "Empty tiles show —.  Descriptive, unadjusted associations—not causal effects.",
             fontsize=9.3, color=MUTED, ha="left", va="top")
    return fig


def save_mortality_heatmap(
    matrix: MortalityMatrix, output_png: Path, *, sparse_n: int = 30, dpi: int = 240
) -> list[Path]:
    """Export raster and editable vector versions of the same figure."""
    if output_png.suffix.lower() != ".png":
        raise ValueError("The --output path must end in .png.")
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig = draw_mortality_heatmap(matrix, sparse_n=sparse_n, dpi=dpi)
    paths = [output_png, output_png.with_suffix(".svg"), output_png.with_suffix(".pdf")]
    for path in paths:
        fig.savefig(path, facecolor=PAPER, dpi=dpi)
    plt.close(fig)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/mortality.xlsx",
                        help="Source Excel workbook, containing a 'model' sheet.")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "figures/04_mortality_heatmap_marginals.png",
                        help="PNG output filename (SVG/PDF versions exported automatically).")
    parser.add_argument("--edges", nargs="+", type=int, default=DEFAULT_DELAY_EDGES,
                        metavar="MIN", help="Upper edges in minutes; the last bin is open-ended.")
    parser.add_argument("--sparse-n", type=int, default=30,
                        help="Flag tiles with fewer than this many visits (default 30).")
    parser.add_argument("--dpi", type=int, default=240, help="PNG resolution (default 240).")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(
            f"Workbook not found: {args.input}. The source workbook isn't in the public repo; "
            "put it at data/raw/mortality.xlsx or use --input PATH."
        )
    from analysis import load_data  # Same complete-case cohort as existing figures.

    _, analysis_data = load_data(args.input)
    matrix = make_mortality_matrix(analysis_data, delay_edges=args.edges)
    outputs = save_mortality_heatmap(matrix, args.output, sparse_n=args.sparse_n, dpi=args.dpi)
    print(f"Aggregated {matrix.total_visits:,} visits / {matrix.total_deaths:,} deaths")
    for path in outputs:
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
