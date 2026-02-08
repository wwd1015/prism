"""Stability metrics: PSI (Population Stability Index), CSI (Characteristic Stability Index)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from prism.metrics.registry import register_metric


def _psi_buckets(
    expected: np.ndarray,
    actual: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Compute PSI across bins.

    Bins are defined by quantiles of the expected distribution.
    """
    # Create bins from expected distribution
    bin_edges = np.quantile(expected, np.linspace(0, 1, n_bins + 1))
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf
    # Remove duplicate edges
    bin_edges = np.unique(bin_edges)

    exp_counts, _ = np.histogram(expected, bins=bin_edges)
    act_counts, _ = np.histogram(actual, bins=bin_edges)

    exp_pct = exp_counts / max(exp_counts.sum(), 1)
    act_pct = act_counts / max(act_counts.sum(), 1)

    # Avoid log(0) by flooring at a small value
    exp_pct = np.maximum(exp_pct, 1e-8)
    act_pct = np.maximum(act_pct, 1e-8)

    psi_per_bin = (act_pct - exp_pct) * np.log(act_pct / exp_pct)

    df = pd.DataFrame(
        {
            "bin": range(1, len(psi_per_bin) + 1),
            "expected_pct": np.round(exp_pct, 6),
            "actual_pct": np.round(act_pct, 6),
            "psi_contribution": np.round(psi_per_bin, 6),
        }
    )
    return df


@register_metric("psi_calculator")
def psi_calculator(
    data: pd.DataFrame,
    score_col: str = "predicted",
    reference_col: str = "reference_score",
    reference_period: str | None = None,
    period_col: str = "period",
    n_bins: int = 10,
    **kwargs,
) -> dict:
    """Calculate Population Stability Index (PSI).

    Compares the distribution of scores between a reference (expected)
    and current (actual) population.

    Args:
        data: DataFrame containing score columns.
        score_col: Column with current scores.
        reference_col: Column with reference/expected scores.
            If not present, uses period_col to split data.
        reference_period: If set, rows with period_col == reference_period
            are used as the reference distribution.
        period_col: Column identifying the time period.
        n_bins: Number of bins for the PSI calculation.

    Returns:
        Dict with psi_value, psi_table, and psi_chart.
    """
    if reference_col in data.columns:
        expected = data[reference_col].dropna().values
        actual = data[score_col].dropna().values
    elif reference_period and period_col in data.columns:
        expected = data.loc[data[period_col] == reference_period, score_col].dropna().values
        actual = data.loc[data[period_col] != reference_period, score_col].dropna().values
    else:
        raise ValueError(
            f"Cannot determine reference distribution: "
            f"need either '{reference_col}' column or "
            f"'{period_col}' column with reference_period set."
        )

    if len(expected) == 0 or len(actual) == 0:
        return {
            "psi_value": 0.0,
            "psi_table": pd.DataFrame(),
            "psi_chart": None,
        }

    psi_table = _psi_buckets(expected, actual, n_bins)
    psi_value = float(psi_table["psi_contribution"].sum())

    # PSI bar chart
    try:
        import plotly.graph_objects as go

        fig = go.Figure(
            data=[
                go.Bar(
                    x=psi_table["bin"],
                    y=psi_table["expected_pct"],
                    name="Expected",
                ),
                go.Bar(
                    x=psi_table["bin"],
                    y=psi_table["actual_pct"],
                    name="Actual",
                ),
            ]
        )
        fig.update_layout(
            title=f"PSI Distribution (PSI = {psi_value:.4f})",
            xaxis_title="Bin",
            yaxis_title="Proportion",
            barmode="group",
        )
    except ImportError:
        fig = None

    return {
        "psi_value": round(psi_value, 6),
        "psi_table": psi_table,
        "psi_chart": fig,
    }


@register_metric("csi_calculator")
def csi_calculator(
    data: pd.DataFrame,
    feature_cols: list[str] | None = None,
    reference_col_suffix: str = "_ref",
    n_bins: int = 10,
    **kwargs,
) -> dict:
    """Calculate Characteristic Stability Index (CSI) across features.

    For each feature, computes PSI between the current and reference
    distribution. The overall CSI is the maximum individual PSI.

    Args:
        data: DataFrame with current and reference feature columns.
        feature_cols: List of feature column names. If None, infers from
            columns that have a corresponding *_ref column.
        reference_col_suffix: Suffix for reference columns.
        n_bins: Number of bins per feature.

    Returns:
        Dict with csi_value (max PSI across features), csi_table, and per-feature detail.
    """
    if feature_cols is None:
        feature_cols = [
            c
            for c in data.columns
            if f"{c}{reference_col_suffix}" in data.columns
        ]

    if not feature_cols:
        return {
            "csi_value": 0.0,
            "csi_table": pd.DataFrame(),
            "feature_details": {},
        }

    results = []
    feature_details = {}
    for col in feature_cols:
        ref_col = f"{col}{reference_col_suffix}"
        if ref_col not in data.columns:
            continue
        expected = data[ref_col].dropna().values
        actual = data[col].dropna().values
        if len(expected) == 0 or len(actual) == 0:
            continue
        psi_table = _psi_buckets(expected, actual, n_bins)
        psi_val = float(psi_table["psi_contribution"].sum())
        results.append({"feature": col, "psi": round(psi_val, 6)})
        feature_details[col] = psi_table

    csi_table = pd.DataFrame(results) if results else pd.DataFrame()
    csi_value = float(csi_table["psi"].max()) if not csi_table.empty else 0.0

    return {
        "csi_value": round(csi_value, 6),
        "csi_table": csi_table,
        "feature_details": feature_details,
    }
