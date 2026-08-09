"""Estimate the association between delayed treatment and mortality in low-severity ED visits.

This module intentionally keeps the estimand, cohort, covariates, diagnostics, and
outputs explicit. It uses cross-fitted augmented inverse probability weighting
(AIPW) and cluster-robust uncertainty at the patient level.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


NUMERIC_COVARIATES = [
    "Severity_Level",
    "Dim_Patient.Age",
    "triage_delay_minutes",
]

CATEGORICAL_COVARIATES = [
    "Hospital_ID",
    "Department_ID",
    "Admission_Type",
    "Diagnosis_Category",
    "Insurance_Type",
    "Ambulance_Arrival_Flag",
    "Dim_Patient.Gender",
    "Dim_Patient.CKD",
    "Dim_Patient.COPD",
    "Dim_Patient.DM2",
    "Dim_Patient.HF",
    "Dim_Patient.Asthma",
    "Dim_Patient.Obesity",
    "Dim_Patient.Hypertension",
    "Dim_Patient.Depression",
    "Dim_Patient.Risk_Category",
]

COVARIATES = NUMERIC_COVARIATES + CATEGORICAL_COVARIATES

BLUE = "#2563EB"
BLUE_LIGHT = "#93C5FD"
ORANGE = "#D97706"
ORANGE_LIGHT = "#FCD34D"
INK = "#172033"
MUTED = "#667085"
GRID = "#D8DEE9"


@dataclass
class Estimate:
    threshold_minutes: int
    n_visits: int
    n_patients: int
    exposed_visits: int
    exposed_deaths: int
    unexposed_visits: int
    unexposed_deaths: int
    crude_risk_exposed: float
    crude_risk_unexposed: float
    crude_risk_difference: float
    adjusted_risk_exposed: float
    adjusted_risk_unexposed: float
    adjusted_risk_difference: float
    standard_error: float
    ci_low: float
    ci_high: float
    propensity_min_raw: float
    propensity_max_raw: float
    propensity_clipped_count: int
    max_weight: float
    weight_p99: float
    ess_exposed: float
    ess_unexposed: float
    max_abs_smd_before: float
    max_abs_smd_after: float
    imbalanced_features_before: int
    imbalanced_features_after: int


def load_analysis_data(workbook_path: Path) -> tuple[pd.DataFrame, dict]:
    """Load the model table, restore patient IDs, and validate the visit grain."""
    model = pd.read_excel(workbook_path, sheet_name="model")
    visits = pd.read_excel(
        workbook_path,
        sheet_name="Fact_Patient_Visits",
        usecols=["Visit_ID", "Patient_ID", "Arrival_DateTime"],
    )

    if model["Visit_ID"].duplicated().any():
        raise ValueError("The model sheet is not unique by Visit_ID.")
    if visits["Visit_ID"].duplicated().any():
        raise ValueError("Fact_Patient_Visits is not unique by Visit_ID.")

    data = model.merge(visits, on="Visit_ID", how="left", validate="one_to_one")
    if data["Patient_ID"].isna().any():
        raise ValueError("Some model visits do not map to a Patient_ID.")

    required = ["Treatment_Delay_Minutes", "Mortality_Flag", *COVARIATES]
    missing_columns = sorted(set(required) - set(data.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    quality = {
        "workbook": workbook_path.name,
        "model_rows": int(len(model)),
        "unique_visits": int(model["Visit_ID"].nunique()),
        "unique_patients": int(data["Patient_ID"].nunique()),
        "duplicate_visit_ids": int(model["Visit_ID"].duplicated().sum()),
        "required_field_nulls": int(data[required].isna().sum().sum()),
        "arrival_date_min": str(pd.to_datetime(data["Arrival_DateTime"]).min()),
        "arrival_date_max": str(pd.to_datetime(data["Arrival_DateTime"]).max()),
        "delay_min": float(data["Treatment_Delay_Minutes"].min()),
        "delay_max": float(data["Treatment_Delay_Minutes"].max()),
        "mortality_events": int(data["Mortality_Flag"].astype(bool).sum()),
    }
    return data, quality


def define_cohort(data: pd.DataFrame, max_severity: int = 3) -> pd.DataFrame:
    """Restrict to severity levels 1 through max_severity and complete analysis rows."""
    cohort = data.loc[data["Severity_Level"].between(1, max_severity)].copy()
    complete = cohort[["Treatment_Delay_Minutes", "Mortality_Flag", "Patient_ID", *COVARIATES]].notna().all(axis=1)
    return cohort.loc[complete].reset_index(drop=True)


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                make_pipeline(SimpleImputer(strategy="median"), StandardScaler()),
                NUMERIC_COVARIATES,
            ),
            (
                "categorical",
                make_pipeline(
                    SimpleImputer(strategy="most_frequent"),
                    OneHotEncoder(handle_unknown="ignore"),
                ),
                CATEGORICAL_COVARIATES,
            ),
        ],
        remainder="drop",
    )


def make_logistic_pipeline() -> object:
    return make_pipeline(
        make_preprocessor(),
        LogisticRegression(C=0.5, max_iter=5_000, solver="lbfgs"),
    )


def cross_fitted_nuisance_predictions(
    x: pd.DataFrame,
    treatment: np.ndarray,
    outcome: np.ndarray,
    groups: np.ndarray,
    folds: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return out-of-fold propensity, treated-risk, and untreated-risk predictions."""
    propensity = np.full(len(x), np.nan)
    outcome_if_exposed = np.full(len(x), np.nan)
    outcome_if_unexposed = np.full(len(x), np.nan)

    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    base_model = make_logistic_pipeline()

    for train_index, test_index in splitter.split(x, treatment, groups):
        x_train = x.iloc[train_index]
        x_test = x.iloc[test_index]
        a_train = treatment[train_index]
        y_train = outcome[train_index]

        if np.unique(a_train).size != 2:
            raise ValueError("A training fold contains only one exposure group.")
        if np.unique(y_train[a_train == 1]).size != 2 or np.unique(y_train[a_train == 0]).size != 2:
            raise ValueError("A training fold contains an exposure group with only one outcome class.")

        ps_model = clone(base_model).fit(x_train, a_train)
        high_model = clone(base_model).fit(x_train.loc[a_train == 1], y_train[a_train == 1])
        low_model = clone(base_model).fit(x_train.loc[a_train == 0], y_train[a_train == 0])

        propensity[test_index] = ps_model.predict_proba(x_test)[:, 1]
        outcome_if_exposed[test_index] = high_model.predict_proba(x_test)[:, 1]
        outcome_if_unexposed[test_index] = low_model.predict_proba(x_test)[:, 1]

    if np.isnan(propensity).any() or np.isnan(outcome_if_exposed).any() or np.isnan(outcome_if_unexposed).any():
        raise RuntimeError("Cross-fitting did not generate predictions for every row.")
    return propensity, outcome_if_exposed, outcome_if_unexposed


def effective_sample_size(weights: np.ndarray) -> float:
    weights = np.asarray(weights, dtype=float)
    return float(weights.sum() ** 2 / np.square(weights).sum())


def weighted_mean_and_variance(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mean = float(np.average(values, weights=weights))
    variance = float(np.average(np.square(values - mean), weights=weights))
    return mean, variance


def standardized_mean_difference(
    values: np.ndarray,
    treatment: np.ndarray,
    weights: np.ndarray | None = None,
) -> float:
    values = np.asarray(values, dtype=float)
    treatment = np.asarray(treatment, dtype=int)
    if weights is None:
        weights = np.ones(len(values), dtype=float)
    weights = np.asarray(weights, dtype=float)

    mean_1, var_1 = weighted_mean_and_variance(values[treatment == 1], weights[treatment == 1])
    mean_0, var_0 = weighted_mean_and_variance(values[treatment == 0], weights[treatment == 0])
    pooled_sd = math.sqrt((var_1 + var_0) / 2)
    return 0.0 if pooled_sd == 0 else (mean_1 - mean_0) / pooled_sd


def calculate_balance(
    cohort: pd.DataFrame,
    treatment: np.ndarray,
    iptw: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict] = []
    for column in NUMERIC_COVARIATES:
        values = pd.to_numeric(cohort[column], errors="coerce").to_numpy()
        rows.append(
            {
                "feature": column,
                "smd_before": standardized_mean_difference(values, treatment),
                "smd_after": standardized_mean_difference(values, treatment, iptw),
            }
        )

    for column in CATEGORICAL_COVARIATES:
        normalized = cohort[column].astype(str).fillna("Missing")
        for level in sorted(normalized.unique()):
            values = normalized.eq(level).astype(float).to_numpy()
            rows.append(
                {
                    "feature": f"{column} = {level}",
                    "smd_before": standardized_mean_difference(values, treatment),
                    "smd_after": standardized_mean_difference(values, treatment, iptw),
                }
            )

    balance = pd.DataFrame(rows)
    balance["abs_smd_before"] = balance["smd_before"].abs()
    balance["abs_smd_after"] = balance["smd_after"].abs()
    return balance.sort_values("abs_smd_before", ascending=False).reset_index(drop=True)


def cluster_robust_standard_error(influence_curve: np.ndarray, groups: np.ndarray) -> float:
    """Compute a one-way cluster-robust standard error for a sample mean."""
    frame = pd.DataFrame({"group": groups, "influence": influence_curve})
    cluster_sums = frame.groupby("group", sort=False)["influence"].sum().to_numpy()
    cluster_count = len(cluster_sums)
    if cluster_count < 2:
        raise ValueError("At least two clusters are required for cluster-robust uncertainty.")
    variance = (cluster_count / (cluster_count - 1)) * np.square(cluster_sums).sum() / len(frame) ** 2
    return float(math.sqrt(variance))


def estimate_effect(
    cohort: pd.DataFrame,
    threshold_minutes: int,
    folds: int = 5,
    seed: int = 42,
) -> tuple[Estimate, pd.DataFrame]:
    x = cohort[COVARIATES].copy()
    treatment = cohort["Treatment_Delay_Minutes"].ge(threshold_minutes).astype(int).to_numpy()
    outcome = cohort["Mortality_Flag"].astype(int).to_numpy()
    groups = cohort["Patient_ID"].astype(str).to_numpy()

    if treatment.sum() == 0 or treatment.sum() == len(treatment):
        raise ValueError(f"Threshold {threshold_minutes} creates an empty exposure group.")

    propensity_raw, m1, m0 = cross_fitted_nuisance_predictions(
        x=x,
        treatment=treatment,
        outcome=outcome,
        groups=groups,
        folds=folds,
        seed=seed,
    )
    propensity = np.clip(propensity_raw, 0.01, 0.99)
    clipped_count = int(np.count_nonzero(propensity != propensity_raw))

    pseudo_1 = m1 + treatment / propensity * (outcome - m1)
    pseudo_0 = m0 + (1 - treatment) / (1 - propensity) * (outcome - m0)
    individual_effect = pseudo_1 - pseudo_0

    risk_1 = float(pseudo_1.mean())
    risk_0 = float(pseudo_0.mean())
    effect = float(individual_effect.mean())
    influence_curve = individual_effect - effect
    standard_error = cluster_robust_standard_error(influence_curve, groups)
    ci_low = effect - 1.96 * standard_error
    ci_high = effect + 1.96 * standard_error

    iptw = np.where(treatment == 1, 1 / propensity, 1 / (1 - propensity))
    balance = calculate_balance(cohort, treatment, iptw)

    exposed = treatment == 1
    unexposed = ~exposed
    crude_risk_1 = float(outcome[exposed].mean())
    crude_risk_0 = float(outcome[unexposed].mean())

    estimate = Estimate(
        threshold_minutes=threshold_minutes,
        n_visits=int(len(cohort)),
        n_patients=int(pd.Series(groups).nunique()),
        exposed_visits=int(exposed.sum()),
        exposed_deaths=int(outcome[exposed].sum()),
        unexposed_visits=int(unexposed.sum()),
        unexposed_deaths=int(outcome[unexposed].sum()),
        crude_risk_exposed=crude_risk_1,
        crude_risk_unexposed=crude_risk_0,
        crude_risk_difference=crude_risk_1 - crude_risk_0,
        adjusted_risk_exposed=risk_1,
        adjusted_risk_unexposed=risk_0,
        adjusted_risk_difference=effect,
        standard_error=standard_error,
        ci_low=ci_low,
        ci_high=ci_high,
        propensity_min_raw=float(propensity_raw.min()),
        propensity_max_raw=float(propensity_raw.max()),
        propensity_clipped_count=clipped_count,
        max_weight=float(iptw.max()),
        weight_p99=float(np.quantile(iptw, 0.99)),
        ess_exposed=effective_sample_size(iptw[exposed]),
        ess_unexposed=effective_sample_size(iptw[unexposed]),
        max_abs_smd_before=float(balance["abs_smd_before"].max()),
        max_abs_smd_after=float(balance["abs_smd_after"].max()),
        imbalanced_features_before=int(balance["abs_smd_before"].ge(0.1).sum()),
        imbalanced_features_after=int(balance["abs_smd_after"].ge(0.1).sum()),
    )
    return estimate, balance


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(GRID)
    axis.tick_params(colors=MUTED)
    axis.title.set_color(INK)
    axis.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.7)
    axis.set_axisbelow(True)


def add_figure_title(figure: plt.Figure, title: str, subtitle: str) -> None:
    figure.suptitle(title, x=0.08, y=0.98, ha="left", fontsize=16, fontweight="bold", color=INK)
    figure.text(0.08, 0.90, subtitle, ha="left", fontsize=10, color=MUTED)


def plot_story_overview(data: pd.DataFrame, cohort: pd.DataFrame, threshold: int, output_path: Path) -> None:
    rows = []
    for label, frame in [("All visits", data), ("Severity levels 1–3", cohort)]:
        high = frame["Treatment_Delay_Minutes"].ge(threshold)
        for group_label, mask in [(f"< {threshold} min", ~high), (f"≥ {threshold} min", high)]:
            rows.append(
                {
                    "scope": label,
                    "delay_group": group_label,
                    "mortality": frame.loc[mask, "Mortality_Flag"].astype(bool).mean() * 100,
                    "visits": int(mask.sum()),
                }
            )
    chart = pd.DataFrame(rows)

    figure, axis = plt.subplots(figsize=(9.5, 5.8))
    x = np.arange(2)
    width = 0.34
    for offset, group_label, color in [(-width / 2, f"< {threshold} min", BLUE_LIGHT), (width / 2, f"≥ {threshold} min", ORANGE)]:
        values = chart.loc[chart["delay_group"].eq(group_label), "mortality"].to_numpy()
        bars = axis.bar(x + offset, values, width, label=group_label, color=color, edgecolor=INK, linewidth=0.5)
        for bar, value in zip(bars, values):
            axis.text(bar.get_x() + bar.get_width() / 2, value + 0.10, f"{value:.2f}%", ha="center", fontsize=10, color=INK)

    axis.set_xticks(x, ["All visits", "Severity levels 1–3"])
    axis.set_ylabel("Observed mortality rate (%)")
    axis.set_ylim(0, max(chart["mortality"]) * 1.28)
    axis.legend(frameon=False, loc="upper right")
    style_axis(axis)
    add_figure_title(
        figure,
        "Crude mortality by treatment-delay group",
        f"All visits versus the prespecified low-severity cohort; high delay is ≥{threshold} minutes",
    )
    figure.subplots_adjust(top=0.84, left=0.10, right=0.96, bottom=0.12)
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_severity_mechanism(data: pd.DataFrame, threshold: int, output_path: Path) -> None:
    """Show why the pooled delay comparison is confounded by severity."""
    frame = data.copy()
    frame["delay_group"] = np.where(
        frame["Treatment_Delay_Minutes"].ge(threshold),
        f"≥ {threshold} min",
        f"< {threshold} min",
    )
    delay_order = [f"< {threshold} min", f"≥ {threshold} min"]
    severity_order = sorted(frame["Severity_Level"].dropna().unique())

    mortality = (
        frame.groupby("Severity_Level")["Mortality_Flag"]
        .mean()
        .mul(100)
        .reindex(severity_order)
    )
    severity_mix = (
        frame.groupby(["delay_group", "Severity_Level"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(index=delay_order, columns=severity_order, fill_value=0)
    )
    severity_mix = severity_mix.div(severity_mix.sum(axis=1), axis=0).mul(100)

    severity_colors = ["#DBEAFE", "#BFDBFE", "#93C5FD", "#60A5FA", "#2563EB"]
    figure, axes = plt.subplots(1, 2, figsize=(11, 5.6), gridspec_kw={"width_ratios": [0.9, 1.25]})

    bars = axes[0].bar(
        np.arange(len(severity_order)),
        mortality.to_numpy(),
        color=BLUE,
        edgecolor=INK,
        linewidth=0.5,
    )
    axes[0].set_xticks(np.arange(len(severity_order)), [str(int(value)) for value in severity_order])
    axes[0].set_xlabel("Severity level")
    axes[0].set_ylabel("Observed mortality rate (%)")
    axes[0].set_ylim(0, mortality.max() * 1.25)
    for bar, value in zip(bars, mortality):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            value + mortality.max() * 0.025,
            f"{value:.1f}%",
            ha="center",
            fontsize=9,
            color=INK,
        )
    axes[0].set_title("Mortality by severity", loc="left", fontsize=12, fontweight="bold")
    style_axis(axes[0])

    bottom = np.zeros(len(delay_order))
    for level, color in zip(severity_order, severity_colors):
        values = severity_mix[level].to_numpy()
        bars = axes[1].bar(
            np.arange(len(delay_order)),
            values,
            bottom=bottom,
            label=f"Level {int(level)}",
            color=color,
            edgecolor="white",
            linewidth=0.7,
        )
        for bar, value, base in zip(bars, values, bottom):
            if value >= 7:
                axes[1].text(
                    bar.get_x() + bar.get_width() / 2,
                    base + value / 2,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=INK if level <= 3 else "white",
                    fontweight="bold",
                )
        bottom += values

    axes[1].set_xticks(np.arange(len(delay_order)), delay_order)
    axes[1].set_xlabel("Treatment-delay group")
    axes[1].set_ylabel("Share of visits within group (%)")
    axes[1].set_ylim(0, 100)
    axes[1].set_title("Severity composition by delay", loc="left", fontsize=12, fontweight="bold")
    axes[1].legend(title="Severity", ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.00), fontsize=8)
    style_axis(axes[1])
    axes[1].grid(axis="x", visible=False)

    add_figure_title(
        figure,
        "Severity, mortality, and treatment timing",
        f"All {len(frame):,} visits; higher-severity visits have higher mortality and are concentrated below {threshold} minutes",
    )
    figure.subplots_adjust(top=0.78, left=0.08, right=0.98, bottom=0.13, wspace=0.30)
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_balance(balance: pd.DataFrame, output_path: Path, top_n: int = 18) -> None:
    display = balance.head(top_n).sort_values("abs_smd_before", ascending=True)
    figure, axis = plt.subplots(figsize=(10, 7.5))
    y = np.arange(len(display))
    axis.hlines(y, display["abs_smd_after"], display["abs_smd_before"], color=GRID, linewidth=1.5)
    axis.scatter(display["abs_smd_before"], y, color=ORANGE, s=46, label="Before weighting", zorder=3)
    axis.scatter(display["abs_smd_after"], y, color=BLUE, s=46, label="After weighting", zorder=3)
    axis.axvline(0.10, color=INK, linewidth=1, linestyle="--", label="0.10 reference")
    readable_labels = (
        display["feature"]
        .str.replace("Dim_Patient.", "Patient ", regex=False)
        .str.replace("_", " ", regex=False)
    )
    axis.set_yticks(y, readable_labels)
    axis.set_xlabel("Absolute standardized mean difference")
    axis.set_xlim(left=0)
    axis.legend(frameon=False, loc="lower right")
    style_axis(axis)
    axis.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.7)
    axis.grid(axis="y", visible=False)
    add_figure_title(
        figure,
        "Measured baseline balance before and after weighting",
        f"Top {min(top_n, len(balance))} imbalances by pre-weighting magnitude; lower is better",
    )
    figure.subplots_adjust(top=0.88, left=0.38, right=0.96, bottom=0.10)
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_effect(primary: Estimate, output_path: Path) -> None:
    labels = ["Crude risk difference", "Adjusted estimate (AIPW)"]
    values = np.array([primary.crude_risk_difference, primary.adjusted_risk_difference]) * 100
    low = np.array([np.nan, primary.ci_low]) * 100
    high = np.array([np.nan, primary.ci_high]) * 100

    figure, axis = plt.subplots(figsize=(9.5, 4.8))
    y = np.array([1, 0])
    axis.axvline(0, color=INK, linewidth=1)
    axis.scatter(values[0], y[0], color=ORANGE, s=70, zorder=3)
    axis.errorbar(
        values[1],
        y[1],
        xerr=[[values[1] - low[1]], [high[1] - values[1]]],
        fmt="o",
        color=BLUE,
        ecolor=BLUE,
        capsize=4,
        markersize=8,
        zorder=3,
    )
    for x_value, y_value in zip(values, y):
        axis.text(x_value, y_value + 0.16, f"{x_value:+.2f} pp", ha="center", color=INK, fontsize=10)
    axis.set_yticks(y, labels)
    axis.set_xlabel("Mortality risk difference (percentage points): high delay − lower delay")
    axis.set_ylim(-0.55, 1.55)
    style_axis(axis)
    axis.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.7)
    axis.grid(axis="y", visible=False)
    add_figure_title(
        figure,
        "Mortality risk difference in low-severity visits",
        f"Severity levels 1–3; high delay is ≥{primary.threshold_minutes} minutes; horizontal interval is the 95% CI",
    )
    figure.subplots_adjust(top=0.82, left=0.27, right=0.96, bottom=0.20)
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_sensitivity(estimates: list[Estimate], output_path: Path) -> None:
    estimates = sorted(estimates, key=lambda value: value.threshold_minutes)
    thresholds = np.array([value.threshold_minutes for value in estimates])
    effects = np.array([value.adjusted_risk_difference for value in estimates]) * 100
    ci_low = np.array([value.ci_low for value in estimates]) * 100
    ci_high = np.array([value.ci_high for value in estimates]) * 100

    figure, axis = plt.subplots(figsize=(9.5, 5.2))
    axis.axhline(0, color=INK, linewidth=1)
    axis.errorbar(
        thresholds,
        effects,
        yerr=[effects - ci_low, ci_high - effects],
        fmt="o-",
        color=BLUE,
        ecolor=BLUE,
        capsize=4,
        markersize=7,
    )
    for x_value, y_value in zip(thresholds, effects):
        axis.text(x_value, y_value + 0.12, f"{y_value:+.2f} pp", ha="center", fontsize=10, color=INK)
    axis.set_xticks(thresholds)
    axis.set_xlabel("High-delay threshold (minutes)")
    axis.set_ylabel("Adjusted mortality risk difference (percentage points)")
    style_axis(axis)
    add_figure_title(
        figure,
        "Threshold sensitivity of the adjusted estimate",
        "Cross-fitted AIPW estimates in severity levels 1–3; vertical intervals are 95% CIs",
    )
    figure.subplots_adjust(top=0.82, left=0.12, right=0.96, bottom=0.16)
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def write_results_markdown(primary: Estimate, quality: dict, output_path: Path) -> None:
    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    text = f"""# Results snapshot

## Headline

In {primary.n_visits:,} low-severity visits (severity levels 1–3), mortality was {pct(primary.crude_risk_exposed)} among visits with treatment delay at or above {primary.threshold_minutes} minutes and {pct(primary.crude_risk_unexposed)} among visits below the threshold. After adjustment with cross-fitted AIPW, the estimated risk difference was {primary.adjusted_risk_difference * 100:+.2f} percentage points (95% CI {primary.ci_low * 100:+.2f} to {primary.ci_high * 100:+.2f}).

This is an observational estimate, not proof that changing delay would cause the estimated change in mortality. The causal interpretation additionally requires consistency, positivity, no interference, correct time ordering, and no unmeasured confounding.

## Cohort and data

- Source: `{quality['workbook']}`, sheets `model` and `Fact_Patient_Visits`
- Source date range: {quality['arrival_date_min']} to {quality['arrival_date_max']}
- Analysis grain: one emergency-department visit
- Eligible cohort: severity levels 1–3 with complete required fields
- Visits: {primary.n_visits:,}; unique patients: {primary.n_patients:,}
- High-delay visits: {primary.exposed_visits:,} ({primary.exposed_deaths:,} deaths)
- Lower-delay visits: {primary.unexposed_visits:,} ({primary.unexposed_deaths:,} deaths)

## Diagnostics

- Maximum absolute SMD: {primary.max_abs_smd_before:.3f} before weighting; {primary.max_abs_smd_after:.3f} after weighting
- Features with |SMD| ≥ 0.10: {primary.imbalanced_features_before} before; {primary.imbalanced_features_after} after
- Raw propensity range: {primary.propensity_min_raw:.3f}–{primary.propensity_max_raw:.3f}
- Propensities clipped to [0.01, 0.99]: {primary.propensity_clipped_count:,}
- 99th percentile / maximum IPTW: {primary.weight_p99:.2f} / {primary.max_weight:.2f}
- Effective sample size: {primary.ess_exposed:.0f} high-delay; {primary.ess_unexposed:.0f} lower-delay

## Interpretation

The descriptive reversal between the full sample and the low-severity cohort is consistent with confounding by severity. The adjusted analysis estimates the average risk difference under the measured-covariate model. Treat the estimate as hypothesis-generating because the delay threshold is operational rather than clinically validated, the outcome is rare, calendar-time and congestion measures are incomplete, and unmeasured confounding remains possible.
"""
    output_path.write_text(text, encoding="utf-8")


def run_analysis(
    workbook_path: Path,
    output_dir: Path,
    threshold: int,
    sensitivity_thresholds: Iterable[int],
    folds: int,
    seed: int,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    results_dir = output_dir / "results"
    reports_dir = output_dir / "reports"
    for directory in (figures_dir, results_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    data, quality = load_analysis_data(workbook_path)
    cohort = define_cohort(data, max_severity=3)

    thresholds = sorted(set([threshold, *sensitivity_thresholds]))
    estimates: list[Estimate] = []
    primary_balance: pd.DataFrame | None = None
    for current_threshold in thresholds:
        estimate, balance = estimate_effect(
            cohort,
            threshold_minutes=current_threshold,
            folds=folds,
            seed=seed,
        )
        estimates.append(estimate)
        if current_threshold == threshold:
            primary_balance = balance

    primary = next(value for value in estimates if value.threshold_minutes == threshold)
    if primary_balance is None:
        raise RuntimeError("Primary balance diagnostics were not generated.")

    summary = {
        "estimand": "ATE risk difference for mortality: delay at/above threshold versus below threshold in severity levels 1–3",
        "primary": asdict(primary),
        "quality": quality,
        "covariates": COVARIATES,
        "assumptions": [
            "consistency",
            "conditional exchangeability given measured baseline covariates",
            "positivity",
            "no interference",
            "correct time ordering and model specification",
        ],
    }

    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (results_dir / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    primary_balance.to_csv(results_dir / "covariate_balance.csv", index=False)
    pd.DataFrame([asdict(value) for value in estimates]).to_csv(
        results_dir / "threshold_sensitivity.csv", index=False
    )

    plot_story_overview(data, cohort, threshold, figures_dir / "01_crude_mortality_reversal.png")
    plot_severity_mechanism(data, threshold, figures_dir / "02_severity_mechanism.png")
    plot_balance(primary_balance, figures_dir / "02_covariate_balance.png")
    plot_effect(primary, figures_dir / "03_effect_estimate.png")
    plot_sensitivity(estimates, figures_dir / "04_threshold_sensitivity.png")
    write_results_markdown(primary, quality, reports_dir / "results.md")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Path to mortality.xlsx")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--threshold", type=int, default=160)
    parser.add_argument("--sensitivity-thresholds", nargs="*", type=int, default=[120, 160, 200])
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = run_analysis(
        workbook_path=arguments.input,
        output_dir=arguments.output_dir,
        threshold=arguments.threshold,
        sensitivity_thresholds=arguments.sensitivity_thresholds,
        folds=arguments.folds,
        seed=arguments.seed,
    )
    primary = result["primary"]
    print(
        "Adjusted risk difference: "
        f"{primary['adjusted_risk_difference'] * 100:+.2f} percentage points "
        f"(95% CI {primary['ci_low'] * 100:+.2f} to {primary['ci_high'] * 100:+.2f})"
    )
