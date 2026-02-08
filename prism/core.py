"""Core Report class: model config loading, pre-compute orchestration.

Implements the two-phase execution pattern:
  Phase 1 (setup.qmd): compute_all() runs every metric and caches results+colors
  Phase 2 (report body): sections access cached data without re-computation
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from prism.colors import compute_all_colors, evaluate_color
from prism.helpers import format_badge, format_scorecard, format_table
from prism.resolver import MetricResolver

logger = logging.getLogger(__name__)


def load_model_config(config_dir: str | Path, model_id: str) -> dict[str, Any]:
    """Load a model's YAML configuration.

    Searches for <config_dir>/models/<model_id>.yaml.

    Args:
        config_dir: Path to the config directory.
        model_id: The model identifier.

    Returns:
        Parsed YAML configuration as a dict.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(config_dir) / "models" / f"{model_id}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Model config not found: {config_path}. "
            f"Create it or check model_id={model_id!r}."
        )
    with open(config_path) as f:
        return yaml.safe_load(f)


class Report:
    """Main interface used inside .qmd files.

    Phase 1 (setup.qmd): Pre-compute all metrics + colors via compute_all()
    Phase 2 (report body): Render sections using cached results

    Usage in a .qmd file:
        ```python
        from prism import Report
        report = Report(model_id="model_a")
        report.compute_all(data=df)
        # Now report.scorecard(), report.final_color(), etc. are all ready.
        ```
    """

    def __init__(
        self,
        model_id: str,
        report_date: str | None = None,
        config_dir: str = "config",
    ):
        self.model_id = model_id
        self.report_date = report_date or date.today().isoformat()
        self.config = load_model_config(config_dir, model_id)
        self.model_name = self.config.get("model_name", model_id)
        self.resolver = MetricResolver()
        self._results: dict[str, dict[str, Any]] = {}
        self._colors: dict[str, Any] = {}
        self._computed = False

    def compute_all(self, data: pd.DataFrame | None = None, **extra_data: Any) -> None:
        """Pre-compute all metrics and colors.

        Called once in setup.qmd before any rendering. After this call,
        all data is cached and available for scorecard(), header(), etc.

        Args:
            data: Primary DataFrame passed to all metrics.
            **extra_data: Additional keyword arguments forwarded to metrics.
        """
        metrics_cfg = self.config.get("metrics", {})
        metric_values: dict[str, float] = {}

        for key, mcfg in metrics_cfg.items():
            metric_id = mcfg["metric_id"]
            source = mcfg.get("source", "local")
            inputs = dict(mcfg.get("inputs", {}))
            if data is not None:
                inputs["data"] = data
            inputs.update(extra_data)

            try:
                result = self.resolver.call(metric_id, source=source, **inputs)
                self._results[key] = result
                # Extract the scalar for color evaluation
                color_field = mcfg.get("color_field")
                if color_field and color_field in result:
                    metric_values[key] = result[color_field]
                logger.info(f"Computed metric {key!r} ({metric_id})")
            except Exception:
                logger.exception(f"Failed to compute metric {key!r} ({metric_id})")
                self._results[key] = {"_error": True}

        # Compute all colors via the color pipeline
        self._colors = compute_all_colors(self.config, metric_values)
        self._computed = True

    def _ensure_computed(self) -> None:
        if not self._computed:
            raise RuntimeError(
                "Report.compute_all() has not been called yet. "
                "Call it in setup.qmd before accessing results."
            )

    # --- Cached accessors ---

    def metric(self, metric_key: str) -> dict[str, Any]:
        """Return the full cached metric result dict.

        Args:
            metric_key: The key from the YAML config (e.g. "rank_ordering").
        """
        self._ensure_computed()
        if metric_key not in self._results:
            raise KeyError(
                f"Metric {metric_key!r} not found. "
                f"Available: {list(self._results.keys())}"
            )
        return self._results[metric_key]

    def metric_value(self, metric_key: str, field: str | None = None) -> Any:
        """Get a specific value from a cached metric result.

        Args:
            metric_key: The key from the YAML config.
            field: The result field to return. If None, uses the color_field
                from the config.
        """
        result = self.metric(metric_key)
        if field is None:
            field = self.config["metrics"][metric_key].get("color_field")
        if field is None:
            raise ValueError(
                f"No field specified and no color_field in config for {metric_key!r}"
            )
        return result.get(field)

    def metric_color(self, metric_key: str) -> str:
        """Get the cached RAG color for a single metric."""
        self._ensure_computed()
        return self._colors.get("metrics", {}).get(metric_key, "green")

    def sector_colors(self) -> dict[str, str]:
        """Get cached sector colors (layer 1 aggregation)."""
        self._ensure_computed()
        return dict(self._colors.get("sectors", {}))

    def final_color(self) -> str:
        """Get the cached final model color (layer 2 matrix aggregation)."""
        self._ensure_computed()
        return self._colors.get("final", "green")

    # --- Rendering Helpers ---

    def scorecard(self) -> str:
        """Render the full scorecard as a markdown table.

        Includes: metric name | sector | value | color badge
        Plus sector subtotals and final model color.
        """
        self._ensure_computed()
        metrics_cfg = self.config.get("metrics", {})
        metrics_data = []
        for key, mcfg in metrics_cfg.items():
            color_field = mcfg.get("color_field")
            value = None
            if key in self._results and color_field:
                value = self._results[key].get(color_field)
            metrics_data.append(
                {
                    "key": key,
                    "name": key.replace("_", " ").title(),
                    "sector": mcfg.get("sector", "default"),
                    "value": value,
                    "color": self._colors.get("metrics", {}).get(key, ""),
                }
            )
        return format_scorecard(
            metrics_data, self.sector_colors(), self.final_color()
        )

    def header(self) -> str:
        """Render report header: model name, date, final color badge."""
        self._ensure_computed()
        color = self.final_color()
        badge = format_badge(color)
        return (
            f"# {self.model_name} — {badge}\n\n"
            f"**Report Date:** {self.report_date} &nbsp;|&nbsp; "
            f"**Model ID:** `{self.model_id}`\n\n---\n"
        )

    def table(self, df: pd.DataFrame, **kwargs: Any) -> str:
        """Render a DataFrame as a formatted markdown table."""
        return format_table(df, **kwargs)

    def chart(self, fig: Any) -> Any:
        """Pass through a Plotly figure (Quarto renders natively)."""
        return fig

    def badge(self, color: str, label: str | None = None) -> str:
        """Render a RAG color badge as inline HTML."""
        return format_badge(color, label)

    def section_header(self, metric_key: str) -> str:
        """Render section header: metric name + individual color badge."""
        self._ensure_computed()
        name = metric_key.replace("_", " ").title()
        color = self.metric_color(metric_key)
        badge = format_badge(color)
        return f"### {name} {badge}\n"
