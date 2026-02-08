"""Accuracy metrics: AUC, accuracy, precision, recall."""

from __future__ import annotations

import numpy as np
import pandas as pd

from prism.metrics.registry import register_metric


def _binary_confusion(
    actuals: np.ndarray, predicted: np.ndarray, threshold: float = 0.5
) -> dict:
    """Compute confusion matrix components."""
    pred_binary = (predicted >= threshold).astype(int)
    tp = int(np.sum((pred_binary == 1) & (actuals == 1)))
    tn = int(np.sum((pred_binary == 0) & (actuals == 0)))
    fp = int(np.sum((pred_binary == 1) & (actuals == 0)))
    fn = int(np.sum((pred_binary == 0) & (actuals == 1)))
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


@register_metric("model_accuracy")
def model_accuracy(
    data: pd.DataFrame,
    actual_col: str = "actual",
    predicted_col: str = "predicted",
    method: str = "auc",
    threshold: float = 0.5,
    **kwargs,
) -> dict:
    """Calculate model accuracy metrics.

    Args:
        data: DataFrame with actual and predicted columns.
        actual_col: Name of the column with actual binary outcomes.
        predicted_col: Name of the column with predicted scores.
        method: Primary metric to report — "auc", "accuracy", "precision", or "recall".
        threshold: Decision threshold for binary classification metrics.

    Returns:
        Dict with auc_value (and other sub-metrics), plus ROC chart.
    """
    actuals = data[actual_col].values
    predicted = data[predicted_col].values

    # AUC via trapezoidal rule on ROC
    sorted_idx = np.argsort(-predicted)
    sorted_actuals = actuals[sorted_idx]
    n_pos = actuals.sum()
    n_neg = len(actuals) - n_pos

    tpr_list = [0.0]
    fpr_list = [0.0]
    tp_running = 0
    fp_running = 0
    for a in sorted_actuals:
        if a == 1:
            tp_running += 1
        else:
            fp_running += 1
        tpr_list.append(tp_running / max(n_pos, 1))
        fpr_list.append(fp_running / max(n_neg, 1))

    auc_value = float(np.trapezoid(tpr_list, fpr_list))

    # Confusion-based metrics
    cm = _binary_confusion(actuals, predicted, threshold)
    total = cm["tp"] + cm["tn"] + cm["fp"] + cm["fn"]
    accuracy_value = (cm["tp"] + cm["tn"]) / max(total, 1)
    precision_value = cm["tp"] / max(cm["tp"] + cm["fp"], 1)
    recall_value = cm["tp"] / max(cm["tp"] + cm["fn"], 1)

    # ROC chart
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=fpr_list, y=tpr_list, mode="lines", name="ROC")
        )
        fig.add_trace(
            go.Scatter(
                x=[0, 1], y=[0, 1], mode="lines", name="Random", line=dict(dash="dash")
            )
        )
        fig.update_layout(
            title=f"ROC Curve (AUC = {auc_value:.4f})",
            xaxis_title="False Positive Rate",
            yaxis_title="True Positive Rate",
        )
    except ImportError:
        fig = None

    # Primary value depends on method
    primary_map = {
        "auc": auc_value,
        "accuracy": accuracy_value,
        "precision": precision_value,
        "recall": recall_value,
    }

    return {
        "auc_value": round(float(auc_value), 6),
        "accuracy_value": round(float(accuracy_value), 6),
        "precision_value": round(float(precision_value), 6),
        "recall_value": round(float(recall_value), 6),
        "confusion_matrix": cm,
        "roc_chart": fig,
        # Convenience: expose the chosen method as a top-level key
        "primary_value": round(float(primary_map.get(method, auc_value)), 6),
    }


@register_metric("precision_recall")
def precision_recall(
    data: pd.DataFrame,
    actual_col: str = "actual",
    predicted_col: str = "predicted",
    threshold: float = 0.5,
    **kwargs,
) -> dict:
    """Calculate precision and recall at a given threshold."""
    actuals = data[actual_col].values
    predicted = data[predicted_col].values
    cm = _binary_confusion(actuals, predicted, threshold)

    precision_value = cm["tp"] / max(cm["tp"] + cm["fp"], 1)
    recall_value = cm["tp"] / max(cm["tp"] + cm["fn"], 1)
    f1 = (
        2 * precision_value * recall_value / max(precision_value + recall_value, 1e-9)
    )

    return {
        "precision_value": round(float(precision_value), 6),
        "recall_value": round(float(recall_value), 6),
        "f1_value": round(float(f1), 6),
        "confusion_matrix": cm,
    }
