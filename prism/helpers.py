"""Formatting helpers for use in .qmd report files.

Provides functions to render DataFrames as markdown tables,
RAG color badges, KPI displays, scorecards, and delta indicators.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from tabulate import tabulate

_COLOR_STYLES = {
    "green": {"symbol": "\u25cf", "hex": "#28a745", "label": "Green"},
    "yellow": {"symbol": "\u25cf", "hex": "#ffc107", "label": "Yellow"},
    "red": {"symbol": "\u25cf", "hex": "#dc3545", "label": "Red"},
}


def format_table(
    df: pd.DataFrame, max_rows: int = 50, precision: int = 4, tablefmt: str = "pipe"
) -> str:
    """Render a DataFrame as a markdown table string.

    Args:
        df: The DataFrame to render.
        max_rows: Maximum number of rows to display.
        precision: Decimal places for float values.
        tablefmt: Table format for tabulate (default: "pipe" for markdown).

    Returns:
        Markdown-formatted table string.
    """
    display_df = df.head(max_rows).copy()
    # Round float columns
    for col in display_df.select_dtypes(include=["float", "float64"]).columns:
        display_df[col] = display_df[col].round(precision)

    table_str = tabulate(
        display_df, headers="keys", tablefmt=tablefmt, showindex=False
    )
    if len(df) > max_rows:
        table_str += f"\n\n*Showing {max_rows} of {len(df)} rows.*"
    return table_str


def format_badge(color: str, label: str | None = None) -> str:
    """Render a RAG color badge as inline HTML.

    Args:
        color: One of "green", "yellow", "red".
        label: Optional text label. Defaults to the color name capitalized.

    Returns:
        Inline HTML span with colored circle and label.
    """
    style = _COLOR_STYLES.get(color, _COLOR_STYLES["red"])
    display_label = label or style["label"]
    return (
        f'<span style="color:{style["hex"]};font-weight:bold;">'
        f'{style["symbol"]} {display_label}</span>'
    )


def format_kpi(
    label: str, value: Any, color: str | None = None, fmt: str | None = None
) -> str:
    """Render a single KPI display with optional color.

    Args:
        label: KPI label text.
        value: The KPI value.
        color: Optional RAG color for the value.
        fmt: Optional format string (e.g. ".2%", ",.0f").

    Returns:
        Markdown/HTML string for the KPI.
    """
    if fmt:
        formatted = f"{value:{fmt}}"
    else:
        formatted = str(value)

    if color:
        style = _COLOR_STYLES.get(color, {})
        hex_color = style.get("hex", "#000")
        return (
            f"**{label}:** "
            f'<span style="color:{hex_color};font-weight:bold;">{formatted}</span>'
        )
    return f"**{label}:** {formatted}"


def format_scorecard(
    metrics_data: list[dict],
    sector_colors: dict[str, str],
    final_color: str,
) -> str:
    """Render the full scorecard table.

    Args:
        metrics_data: List of dicts with keys: key, name, sector, value, color.
        sector_colors: Mapping of sector → aggregated color.
        final_color: The final model color.

    Returns:
        Markdown table with metric rows, sector subtotals, and final color.
    """
    lines = [
        "| Metric | Sector | Value | Status |",
        "|--------|--------|------:|--------|",
    ]

    # Group by sector for subtotal rows
    current_sector = None
    for m in metrics_data:
        sector = m["sector"]
        if sector != current_sector and current_sector is not None:
            # Insert sector subtotal for the previous sector
            sc = sector_colors.get(current_sector, "")
            if sc:
                badge = format_badge(sc)
                lines.append(
                    f"| **{current_sector.replace('_', ' ').title()}** | "
                    f"*Sector Rating* | | {badge} |"
                )
                lines.append("| | | | |")
            current_sector = sector
        elif current_sector is None:
            current_sector = sector

        # Format value
        val = m.get("value")
        if val is not None and isinstance(val, float):
            val_str = f"{val:.4f}"
        elif val is not None:
            val_str = str(val)
        else:
            val_str = "—"

        color_badge = format_badge(m["color"]) if m.get("color") else ""
        lines.append(
            f"| {m['name']} | {sector.replace('_', ' ').title()} | {val_str} | {color_badge} |"
        )

    # Final sector subtotal
    if current_sector and current_sector in sector_colors:
        sc = sector_colors[current_sector]
        badge = format_badge(sc)
        lines.append(
            f"| **{current_sector.replace('_', ' ').title()}** | "
            f"*Sector Rating* | | {badge} |"
        )

    # Final model color
    lines.append("| | | | |")
    final_badge = format_badge(final_color)
    lines.append(f"| **Overall Model Rating** | | | {final_badge} |")

    return "\n".join(lines)


def format_delta(current: float, previous: float, fmt: str = "pct") -> str:
    """Render a change indicator: arrow + formatted delta.

    Args:
        current: Current value.
        previous: Previous value.
        fmt: Format type — "pct" for percentage, "abs" for absolute.

    Returns:
        String like "▲ 5.2%" or "▼ -3.1%".
    """
    diff = current - previous

    if fmt == "pct" and previous != 0:
        pct = (diff / abs(previous)) * 100
        arrow = "\u25b2" if pct >= 0 else "\u25bc"
        return f"{arrow} {pct:+.1f}%"
    else:
        arrow = "\u25b2" if diff >= 0 else "\u25bc"
        return f"{arrow} {diff:+.4f}"
