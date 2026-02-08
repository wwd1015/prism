"""RAG color determination and multi-layer aggregation.

Provides threshold evaluation for individual metrics, sector-level
aggregation (worst_color, best_color, majority), and a matrix-based
final color aggregation across sectors.
"""

from __future__ import annotations

import operator
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

# Canonical ordering from best to worst
COLOR_ORDER = {"green": 0, "yellow": 1, "red": 2}
ORDER_TO_COLOR = {v: k for k, v in COLOR_ORDER.items()}

_OPERATOR_MAP = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

_THRESHOLD_RE = re.compile(r"^\s*(>=|<=|>|<|==|!=)\s*([+-]?\d+(?:\.\d+)?)\s*$")


def parse_threshold(expr: str) -> Callable[[float], bool]:
    """Parse a threshold expression like '>= 0.4' into a callable predicate.

    Args:
        expr: A string of the form '<op> <number>', e.g. '>= 0.4', '< 0.3'.

    Returns:
        A callable that takes a float and returns bool.

    Raises:
        ValueError: If the expression cannot be parsed.
    """
    match = _THRESHOLD_RE.match(expr)
    if not match:
        raise ValueError(f"Invalid threshold expression: {expr!r}")
    op_str, val_str = match.groups()
    op_fn = _OPERATOR_MAP[op_str]
    val = float(val_str)
    return lambda x, _op=op_fn, _val=val: _op(x, _val)


def evaluate_color(value: float, thresholds: dict[str, str]) -> str:
    """Apply threshold rules to determine RAG color.

    Evaluates thresholds in priority order: green first, then yellow,
    then red. Returns the first matching color.

    Args:
        value: The numeric value to evaluate.
        thresholds: Mapping of color → threshold expression,
            e.g. {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"}.

    Returns:
        One of "green", "yellow", or "red".

    Raises:
        ValueError: If no threshold matches the value.
    """
    for color in ("green", "yellow", "red"):
        if color in thresholds:
            predicate = parse_threshold(thresholds[color])
            if predicate(value):
                return color
    raise ValueError(
        f"No threshold matched for value={value} with thresholds={thresholds}"
    )


def aggregate_sector(metric_colors: list[str], method: str = "worst_color") -> str:
    """Aggregate metric colors within a sector.

    Args:
        metric_colors: List of color strings ("green", "yellow", "red").
        method: Aggregation method - "worst_color", "best_color", or "majority".

    Returns:
        The aggregated color string.

    Raises:
        ValueError: If metric_colors is empty or method is unknown.
    """
    if not metric_colors:
        raise ValueError("Cannot aggregate empty list of colors")

    if method == "worst_color":
        return ORDER_TO_COLOR[max(COLOR_ORDER[c] for c in metric_colors)]
    elif method == "best_color":
        return ORDER_TO_COLOR[min(COLOR_ORDER[c] for c in metric_colors)]
    elif method == "majority":
        counts = Counter(metric_colors)
        # Tie-break: worst color wins (higher COLOR_ORDER = worse)
        return max(counts, key=lambda c: (counts[c], COLOR_ORDER[c]))
    else:
        raise ValueError(f"Unknown sector aggregation method: {method!r}")


def aggregate_matrix(
    sector_colors: dict[str, str],
    dimensions: list[str],
    matrix: dict[str, dict[str, str]],
) -> str:
    """Iteratively apply 2D mapping matrix across sector colors.

    For N dimensions, applies the matrix pairwise:
      step 1: matrix[dim1_color][dim2_color] → intermediate
      step 2: matrix[intermediate][dim3_color] → final
      ...

    Args:
        sector_colors: Mapping of sector name → color string.
        dimensions: Ordered list of sector names to aggregate.
        matrix: 2D color mapping, e.g. matrix["green"]["yellow"] → "yellow".

    Returns:
        The final aggregated color string.

    Raises:
        ValueError: If dimensions has fewer than 2 entries.
        KeyError: If a sector name is missing from sector_colors.
    """
    if len(dimensions) < 2:
        raise ValueError("Matrix aggregation requires at least 2 dimensions")

    result = sector_colors[dimensions[0]]
    for dim in dimensions[1:]:
        other = sector_colors[dim]
        result = matrix[result][other]
    return result


def compute_all_colors(
    config: dict[str, Any],
    metric_values: dict[str, float],
) -> dict[str, Any]:
    """Full pipeline: metric values → metric colors → sector colors → final.

    Args:
        config: The full model config dict (must contain 'metrics' and 'aggregation').
        metric_values: Mapping of metric_key → numeric value (already extracted
            via each metric's color_field).

    Returns:
        {
            "metrics": {"rank_ordering": "green", "psi": "yellow", ...},
            "sectors": {"discriminatory_power": "green", "stability": "yellow", ...},
            "final": "yellow"
        }
    """
    metrics_cfg = config["metrics"]
    agg_cfg = config.get("aggregation", {})

    # Step 1: Evaluate individual metric colors
    metric_colors: dict[str, str] = {}
    for key, mcfg in metrics_cfg.items():
        if key not in metric_values:
            continue
        metric_colors[key] = evaluate_color(metric_values[key], mcfg["color"])

    # Step 2: Group by sector and aggregate
    sector_method = agg_cfg.get("sector", {}).get("method", "worst_color")
    sectors: dict[str, list[str]] = {}
    for key, mcfg in metrics_cfg.items():
        sector = mcfg.get("sector", "default")
        if key in metric_colors:
            sectors.setdefault(sector, []).append(metric_colors[key])

    sector_colors: dict[str, str] = {}
    for sector, colors in sectors.items():
        sector_colors[sector] = aggregate_sector(colors, sector_method)

    # Step 3: Final aggregation via matrix (if configured)
    final_cfg = agg_cfg.get("final", {})
    if final_cfg.get("method") == "matrix":
        dimensions = final_cfg["dimensions"]
        matrix = final_cfg["matrix"]
        # Only include dimensions that have sector colors
        active_dims = [d for d in dimensions if d in sector_colors]
        if len(active_dims) >= 2:
            final = aggregate_matrix(sector_colors, active_dims, matrix)
        elif len(active_dims) == 1:
            final = sector_colors[active_dims[0]]
        else:
            final = "green"
    else:
        # Default: worst_color across all sectors
        if sector_colors:
            final = aggregate_sector(list(sector_colors.values()), "worst_color")
        else:
            final = "green"

    return {
        "metrics": metric_colors,
        "sectors": sector_colors,
        "final": final,
    }
