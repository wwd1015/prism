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

# Numeric scores for weighted averaging
COLOR_SCORE = {"green": 3, "yellow": 2, "red": 1}

# Default thresholds for weighted_average → color conversion
DEFAULT_WEIGHTED_THRESHOLDS = {"green": ">= 2.5", "yellow": ">= 1.5", "red": "< 1.5"}

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


def aggregate_sector_weighted(
    metric_colors: dict[str, str],
    weights: dict[str, float],
    thresholds: dict[str, str] | None = None,
) -> str:
    """Aggregate metric colors using a weighted average.

    Colors are scored (green=3, yellow=2, red=1), a weighted average is
    computed, then converted back to a color via thresholds.

    Args:
        metric_colors: Mapping of metric_key → color string.
        weights: Mapping of metric_key → weight (must cover all keys in metric_colors).
        thresholds: Optional score→color thresholds. Defaults to >=2.5 green, >=1.5 yellow.

    Returns:
        The aggregated color string.

    Raises:
        ValueError: If metric_colors is empty or a metric has no weight.
    """
    if not metric_colors:
        raise ValueError("Cannot aggregate empty dict of colors")

    if thresholds is None:
        thresholds = DEFAULT_WEIGHTED_THRESHOLDS

    total_weight = 0.0
    weighted_sum = 0.0
    for key, color in metric_colors.items():
        if key not in weights:
            raise ValueError(f"No weight defined for metric {key!r}")
        w = weights[key]
        weighted_sum += COLOR_SCORE[color] * w
        total_weight += w

    if total_weight == 0:
        raise ValueError("Total weight is zero")

    avg = weighted_sum / total_weight
    return evaluate_color(avg, thresholds)


def parse_matrix_rules(
    rules: list[str],
    num_dimensions: int,
) -> dict[tuple[str, ...], str]:
    """Parse rule strings into a lookup dict keyed by color tuples.

    Each rule has the form: "color1 | color2 | ... = result"
    Supports '*' as a wildcard matching any color.

    Args:
        rules: List of rule strings.
        num_dimensions: Expected number of input dimensions.

    Returns:
        Dict mapping tuples of colors (or '*') to result color.

    Raises:
        ValueError: If a rule is malformed or dimension count mismatches.
    """
    parsed: dict[tuple[str, ...], str] = {}
    valid_tokens = {"green", "yellow", "red", "*"}
    valid_results = {"green", "yellow", "red"}

    for rule in rules:
        if "=" not in rule:
            raise ValueError(f"Invalid rule (missing '='): {rule!r}")
        lhs, rhs = rule.rsplit("=", 1)
        result = rhs.strip()
        if result not in valid_results:
            raise ValueError(f"Invalid result color {result!r} in rule: {rule!r}")
        parts = [p.strip() for p in lhs.split("|")]
        if len(parts) != num_dimensions:
            raise ValueError(
                f"Rule has {len(parts)} dimensions, expected {num_dimensions}: {rule!r}"
            )
        for p in parts:
            if p not in valid_tokens:
                raise ValueError(f"Invalid color {p!r} in rule: {rule!r}")
        key = tuple(parts)
        parsed[key] = result

    return parsed


def aggregate_matrix_rules(
    sector_colors: dict[str, str],
    dimensions: list[str],
    rules: dict[tuple[str, ...], str],
) -> str:
    """Look up the final color from parsed rules, with wildcard fallback.

    Tries exact match first, then progressively replaces dimensions with '*'
    (fewest wildcards first) until a match is found.

    Args:
        sector_colors: Mapping of sector name → color string.
        dimensions: Ordered list of sector names.
        rules: Parsed rules dict from parse_matrix_rules().

    Returns:
        The matched result color.

    Raises:
        KeyError: If no rule matches the input colors.
    """
    from itertools import combinations

    colors = tuple(sector_colors[d] for d in dimensions)
    n = len(colors)

    # Try from 0 wildcards to n wildcards
    for num_wildcards in range(n + 1):
        if num_wildcards == 0:
            if colors in rules:
                return rules[colors]
        else:
            for positions in combinations(range(n), num_wildcards):
                key = list(colors)
                for pos in positions:
                    key[pos] = "*"
                t = tuple(key)
                if t in rules:
                    return rules[t]

    raise KeyError(
        f"No rule matched for colors {dict(zip(dimensions, colors))}"
    )


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
    sector_cfg = agg_cfg.get("sector", {})
    default_sector_method = sector_cfg.get("method", "worst_color")
    sector_overrides = sector_cfg.get("overrides", {})

    # Build dict of sector → {metric_key: color}
    sectors: dict[str, dict[str, str]] = {}
    for key, mcfg in metrics_cfg.items():
        sector = mcfg.get("sector", "default")
        if key in metric_colors:
            sectors.setdefault(sector, {})[key] = metric_colors[key]

    sector_colors: dict[str, str] = {}
    for sector, colors_map in sectors.items():
        override = sector_overrides.get(sector, {})
        method = override.get("method", default_sector_method)

        if method == "weighted_average":
            sector_colors[sector] = aggregate_sector_weighted(
                colors_map,
                override["weights"],
                override.get("thresholds"),
            )
        elif method == "matrix":
            dims = override["dimensions"]
            parsed = parse_matrix_rules(override["rules"], len(dims))
            sector_colors[sector] = aggregate_matrix_rules(colors_map, dims, parsed)
        else:
            # worst_color, best_color, majority
            sector_colors[sector] = aggregate_sector(
                list(colors_map.values()), method
            )

    # Step 3: Final aggregation via matrix (if configured)
    final_cfg = agg_cfg.get("final", {})
    if final_cfg.get("method") == "matrix":
        dimensions = final_cfg["dimensions"]
        # Only include dimensions that have sector colors
        active_dims = [d for d in dimensions if d in sector_colors]
        parsed = parse_matrix_rules(final_cfg["rules"], len(dimensions))
        if len(active_dims) >= 2:
            final = aggregate_matrix_rules(sector_colors, active_dims, parsed)
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
