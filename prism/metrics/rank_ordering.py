"""Rank ordering metrics: Gini coefficient, KS statistic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from prism.metrics.registry import register_metric


@register_metric("gini_coefficient")
def gini_coefficient(
    data: pd.DataFrame,
    actual_col: str = "actual",
    predicted_col: str = "predicted",
    segment: str = "all",
    **kwargs,
) -> dict:
    """Calculate Gini coefficient for model discriminatory power.

    Args:
        data: DataFrame with actual and predicted columns.
        actual_col: Name of the column with actual outcomes.
        predicted_col: Name of the column with predicted scores.
        segment: Segment filter; "all" uses the full dataset.

    Returns:
        Dict with gini_value, summary DataFrame, and lorenz_chart.
    """
    df = data if segment == "all" else data[data["segment"] == segment]

    actuals = df[actual_col].values
    predicted = df[predicted_col].values

    # Sort by predicted score descending
    sorted_idx = np.argsort(-predicted)
    sorted_actuals = actuals[sorted_idx]

    n = len(sorted_actuals)
    cumulative_actuals = np.cumsum(sorted_actuals)
    total_actuals = cumulative_actuals[-1] if cumulative_actuals[-1] != 0 else 1

    # Lorenz curve points
    lorenz_y = np.concatenate([[0], cumulative_actuals / total_actuals])
    lorenz_x = np.linspace(0, 1, n + 1)

    # Gini = 2 * (AUC of Lorenz - 0.5)
    auc_lorenz = np.trapezoid(lorenz_y, lorenz_x)
    gini_value = 2 * auc_lorenz - 1

    # Summary by decile
    df_sorted = df.iloc[sorted_idx].copy()
    df_sorted["decile"] = pd.qcut(range(n), 10, labels=False, duplicates="drop") + 1
    summary = (
        df_sorted.groupby("decile")
        .agg(
            count=(actual_col, "count"),
            event_rate=(actual_col, "mean"),
            avg_score=(predicted_col, "mean"),
        )
        .reset_index()
    )

    # Lorenz chart (Plotly)
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=lorenz_x, y=lorenz_y, mode="lines", name="Model")
        )
        fig.add_trace(
            go.Scatter(
                x=[0, 1], y=[0, 1], mode="lines", name="Random", line=dict(dash="dash")
            )
        )
        fig.update_layout(
            title=f"Lorenz Curve (Gini = {gini_value:.4f})",
            xaxis_title="Cumulative % of Population",
            yaxis_title="Cumulative % of Events",
        )
    except ImportError:
        fig = None

    return {
        "gini_value": round(float(gini_value), 6),
        "summary": summary,
        "lorenz_chart": fig,
    }


@register_metric("ks_statistic")
def ks_statistic(
    data: pd.DataFrame,
    actual_col: str = "actual",
    predicted_col: str = "predicted",
    **kwargs,
) -> dict:
    """Calculate KS (Kolmogorov-Smirnov) statistic.

    Args:
        data: DataFrame with actual and predicted columns.
        actual_col: Name of the column with actual outcomes.
        predicted_col: Name of the column with predicted scores.

    Returns:
        Dict with ks_value and ks_table.
    """
    df = data.copy()
    df = df.sort_values(predicted_col, ascending=False).reset_index(drop=True)

    n = len(df)
    df["decile"] = pd.qcut(range(n), 10, labels=False, duplicates="drop") + 1

    events = df[actual_col].sum()
    non_events = n - events

    ks_table = (
        df.groupby("decile")
        .agg(
            count=(actual_col, "count"),
            events=(actual_col, "sum"),
        )
        .reset_index()
    )
    ks_table["non_events"] = ks_table["count"] - ks_table["events"]
    ks_table["cum_event_rate"] = ks_table["events"].cumsum() / max(events, 1)
    ks_table["cum_non_event_rate"] = ks_table["non_events"].cumsum() / max(non_events, 1)
    ks_table["ks"] = abs(ks_table["cum_event_rate"] - ks_table["cum_non_event_rate"])

    ks_value = float(ks_table["ks"].max())

    return {
        "ks_value": round(ks_value, 6),
        "ks_table": ks_table,
    }
