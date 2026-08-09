"""Doubly robust analysis of ED treatment delay and mortality."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CONFOUNDERS = ["Severity_Level", "Dim_Patient.Age"]
BLUE, LIGHT_BLUE, ORANGE, INK, MUTED, GRID = (
    "#2563EB", "#93C5FD", "#D97706", "#172033", "#667085", "#D8DEE9"
)


def load_data(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_excel(path, sheet_name="model")
    needed = ["Treatment_Delay_Minutes", "Mortality_Flag", *CONFOUNDERS]
    if missing := sorted(set(needed) - set(data.columns)):
        raise ValueError(f"Missing columns: {missing}")
    analysis_data = data[needed].dropna().copy()
    return data, analysis_data.reset_index(drop=True)


def model():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=2_000),
    )


def estimate_aipw(data: pd.DataFrame, threshold: int = 160, seed: int = 1) -> dict:
    """Cross-fitted propensity and outcome models with the standard AIPW formula."""
    x = data[CONFOUNDERS]
    a = data["Treatment_Delay_Minutes"].ge(threshold).astype(int).to_numpy()
    y = data["Mortality_Flag"].astype(int).to_numpy()
    propensity = np.empty(len(data))
    m1 = np.empty(len(data))
    m0 = np.empty(len(data))

    folds = StratifiedKFold(5, shuffle=True, random_state=seed)
    for train, test in folds.split(x, a):
        propensity_model = model().fit(x.iloc[train], a[train])
        high_model = model().fit(x.iloc[train][a[train] == 1], y[train][a[train] == 1])
        low_model = model().fit(x.iloc[train][a[train] == 0], y[train][a[train] == 0])
        propensity[test] = propensity_model.predict_proba(x.iloc[test])[:, 1]
        m1[test] = high_model.predict_proba(x.iloc[test])[:, 1]
        m0[test] = low_model.predict_proba(x.iloc[test])[:, 1]

    propensity = np.clip(propensity, 0.01, 0.99)
    weights = np.where(a == 1, 1 / propensity, 1 / (1 - propensity))

    # Doubly robust AIPW: propensity model + mortality outcome models.
    psi1 = np.mean(m1 + (y - m1) * weights * a)
    psi0 = np.mean(m0 + (y - m0) * weights * (1 - a))

    return {
        "risk_high": float(psi1),
        "risk_low": float(psi0),
        "risk_difference": float(psi1 - psi0),
        "crude_high": float(y[a == 1].mean()),
        "crude_low": float(y[a == 0].mean()),
        "n": int(len(data)),
        "high_n": int(a.sum()),
        "low_n": int((1 - a).sum()),
        "deaths": int(y.sum()),
    }


def bootstrap_ci(
    data: pd.DataFrame,
    threshold: int = 160,
    bootstraps: int = 200,
    seed: int = 42,
) -> tuple[float, float]:
    """Simple row bootstrap that refits the complete AIPW estimator."""
    rng = np.random.default_rng(seed)
    effects = []
    for b in range(bootstraps):
        sample = data.iloc[rng.integers(0, len(data), len(data))].reset_index(drop=True)
        effects.append(estimate_aipw(sample, threshold, seed + b)["risk_difference"])
    return tuple(np.percentile(effects, [2.5, 97.5]))


def figure_title(fig, title: str, subtitle: str) -> None:
    fig.suptitle(title, x=0.07, y=0.98, ha="left", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.07, 0.90, subtitle, ha="left", fontsize=10, color=MUTED)


def style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED)


def plot_reversal(data: pd.DataFrame, threshold: int, path: Path) -> None:
    rows = []
    populations = [("All visits", data)] + [
        (f"Level {int(level)}", data.loc[data["Severity_Level"].eq(level)])
        for level in sorted(data["Severity_Level"].dropna().unique())
    ]
    for population, frame in populations:
        high = frame["Treatment_Delay_Minutes"].ge(threshold)
        for delay, mask in [(f"< {threshold} min", ~high), (f">= {threshold} min", high)]:
            rows.append((population, delay, frame.loc[mask, "Mortality_Flag"].mean() * 100))
    chart = pd.DataFrame(rows, columns=["population", "delay", "mortality"])

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x, width = np.arange(len(populations)), 0.34
    for offset, delay, color in [(-width / 2, f"< {threshold} min", LIGHT_BLUE), (width / 2, f">= {threshold} min", ORANGE)]:
        values = chart.loc[chart["delay"].eq(delay), "mortality"]
        bars = ax.bar(x + offset, values, width, label=delay, color=color, edgecolor=INK, linewidth=0.5)
        ax.bar_label(bars, fmt="%.2f%%", padding=4)
    ax.set_xticks(x, [name for name, _ in populations])
    ax.set_ylabel("Observed mortality (%)")
    ax.set_ylim(0, chart["mortality"].max() * 1.3)
    ax.legend(frameon=False)
    style(ax)
    figure_title(fig, "The pooled average hides the within-severity pattern", "All five severity levels remain in the analysis")
    fig.subplots_adjust(top=0.82, left=0.10, right=0.96, bottom=0.12)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_severity(data: pd.DataFrame, threshold: int, path: Path) -> None:
    frame = data.assign(
        delay=np.where(data["Treatment_Delay_Minutes"].ge(threshold), f"≥ {threshold} min", f"< {threshold} min")
    )
    order = sorted(frame["Severity_Level"].dropna().unique())
    mortality = frame.groupby("Severity_Level")["Mortality_Flag"].mean().mul(100).reindex(order)
    mix = pd.crosstab(frame["delay"], frame["Severity_Level"], normalize="index").mul(100)
    mix = mix.reindex([f"< {threshold} min", f"≥ {threshold} min"], columns=order, fill_value=0)
    colors = ["#DBEAFE", "#BFDBFE", "#93C5FD", "#60A5FA", BLUE]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), gridspec_kw={"width_ratios": [0.9, 1.1]})
    bars = axes[0].bar(order, mortality, color=BLUE, edgecolor=INK, linewidth=0.5)
    axes[0].bar_label(bars, fmt="%.1f%%", padding=4)
    axes[0].set(xlabel="Severity level", ylabel="Observed mortality (%)", title="Mortality by severity")
    axes[0].set_ylim(0, mortality.max() * 1.25)
    style(axes[0])

    bottom = np.zeros(2)
    for level, color in zip(order, colors):
        values = mix[level].to_numpy()
        bars = axes[1].bar(range(2), values, bottom=bottom, label=f"Level {int(level)}", color=color, edgecolor="white")
        for bar, value, base in zip(bars, values, bottom):
            if value >= 7:
                axes[1].text(bar.get_x() + bar.get_width() / 2, base + value / 2, f"{value:.0f}%", ha="center", va="center", fontweight="bold", color=INK if level <= 3 else "white")
        bottom += values
    axes[1].set_xticks(range(2), mix.index)
    axes[1].set(xlabel="Treatment-delay group", ylabel="Share within group (%)", title="Severity composition by delay")
    axes[1].legend(title="Severity", frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    style(axes[1])
    axes[1].grid(axis="x", visible=False)
    figure_title(fig, "Severity drives the crude comparison", f"All {len(frame):,} visits; high-severity visits are treated sooner and die more often")
    fig.subplots_adjust(top=0.78, left=0.07, right=0.84, bottom=0.13, wspace=0.30)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_effect(result: dict, path: Path) -> None:
    crude = (result["crude_high"] - result["crude_low"]) * 100
    adjusted = result["risk_difference"] * 100
    low, high = result["ci_low"] * 100, result["ci_high"] * 100
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axvline(0, color=INK, linewidth=1)
    ax.scatter(crude, 1, color=ORANGE, s=70)
    ax.errorbar(adjusted, 0, xerr=[[adjusted - low], [high - adjusted]], fmt="o", color=BLUE, capsize=4, markersize=8)
    ax.text(crude, 1.15, f"{crude:+.2f} pp", ha="center", color=INK)
    ax.text(adjusted, 0.15, f"{adjusted:+.2f} pp", ha="center", color=INK)
    ax.set_yticks([1, 0], ["Crude", "Doubly robust AIPW"])
    ax.set_xlabel("Mortality risk difference (percentage points): high delay - lower delay")
    ax.set_ylim(-0.55, 1.55)
    style(ax)
    ax.grid(axis="x", color=GRID)
    ax.grid(axis="y", visible=False)
    figure_title(fig, "Adjusted mortality risk difference across all visits", "High delay is >=160 minutes; horizontal interval is the bootstrap 95% CI")
    fig.subplots_adjust(top=0.80, left=0.25, right=0.96, bottom=0.20)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def run_analysis(path: Path, output: Path, threshold: int = 160, bootstraps: int = 200) -> dict:
    figures, results, reports = output / "figures", output / "results", output / "reports"
    for folder in (figures, results, reports):
        folder.mkdir(parents=True, exist_ok=True)

    data, analysis_data = load_data(path)
    estimate = estimate_aipw(analysis_data, threshold)
    estimate["ci_low"], estimate["ci_high"] = bootstrap_ci(analysis_data, threshold, bootstraps)
    estimate.update({"threshold": threshold, "bootstraps": bootstraps, "confounders": CONFOUNDERS})

    (results / "summary.json").write_text(json.dumps(estimate, indent=2), encoding="utf-8")
    (reports / "results.md").write_text(
        "# Results\n\n"
        f"Among {estimate['n']:,} visits across severity levels 1-5, the doubly robust AIPW risk difference was "
        f"**{estimate['risk_difference'] * 100:+.2f} percentage points** "
        f"(bootstrap 95% CI {estimate['ci_low'] * 100:+.2f} to {estimate['ci_high'] * 100:+.2f}).\n",
        encoding="utf-8",
    )
    plot_reversal(analysis_data, threshold, figures / "01_crude_mortality_reversal.png")
    plot_severity(analysis_data, threshold, figures / "02_severity_mechanism.png")
    plot_effect(estimate, figures / "03_effect_estimate.png")
    return estimate


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--threshold", type=int, default=160)
    parser.add_argument("--bootstraps", type=int, default=200)
    args = parser.parse_args()
    result = run_analysis(args.input, args.output_dir, args.threshold, args.bootstraps)
    print(
        f"AIPW risk difference: {result['risk_difference'] * 100:+.2f} pp "
        f"(95% CI {result['ci_low'] * 100:+.2f} to {result['ci_high'] * 100:+.2f})"
    )
