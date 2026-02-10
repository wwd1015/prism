"""Metric resolver: routes metric calls to local functions or CAP.

Resolution order:
1. If source="cap" and CAP is installed → use cap.call_metric()
2. If source="local" or source not specified → use local registry
3. If source="cap" but CAP not installed → warn + fallback to local
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from prism.metrics.registry import get_metric, list_metrics

logger = logging.getLogger(__name__)


def _check_cap_available() -> bool:
    """Check if the CAP package is importable."""
    try:
        import cap  # noqa: F401

        return True
    except ImportError:
        return False


class MetricResolver:
    """Routes metric calls to local functions or CAP.

    Usage:
        resolver = MetricResolver()
        result = resolver.call("gini_coefficient", source="local", data=df)
    """

    def __init__(self, connector=None):
        self.connector = connector
        self._cap_available = _check_cap_available()
        if self._cap_available:
            logger.info("CAP package detected — cap-sourced metrics enabled")

    def call(
        self, metric_id: str, source: str = "local", **inputs: Any
    ) -> dict[str, Any]:
        """Call a metric by ID, routing to the appropriate backend.

        Args:
            metric_id: The registered metric identifier.
            source: "local" to use built-in metrics, "cap" to use CAP.
            **inputs: Keyword arguments forwarded to the metric function.

        Returns:
            The metric result dict.

        Raises:
            ValueError: If the metric is not found in any available backend.
        """
        if self.connector is not None:
            inputs.setdefault("connector", self.connector)

        if source == "cap":
            if self._cap_available:
                return self._call_cap(metric_id, **inputs)
            else:
                warnings.warn(
                    f"source='cap' requested for {metric_id!r} but CAP is not installed. "
                    f"Falling back to local implementation.",
                    stacklevel=2,
                )
                return self._call_local(metric_id, **inputs)

        return self._call_local(metric_id, **inputs)

    def _call_local(self, metric_id: str, **inputs: Any) -> dict[str, Any]:
        """Invoke a locally registered metric function."""
        fn = get_metric(metric_id)
        if fn is None:
            available = list_metrics()
            raise ValueError(
                f"Metric {metric_id!r} not found in local registry. "
                f"Available: {available}"
            )
        return fn(**inputs)

    def _call_cap(self, metric_id: str, **inputs: Any) -> dict[str, Any]:
        """Invoke a metric via the CAP package."""
        import cap  # noqa: F811

        return cap.call_metric(metric_id, **inputs)

    def available_metrics(self) -> dict[str, list[str]]:
        """List all available metrics with their source.

        Returns:
            Dict mapping metric_id → list of available sources
            (e.g. {"gini_coefficient": ["local"], "some_cap_metric": ["cap"]}).
        """
        result: dict[str, list[str]] = {}
        for mid in list_metrics():
            result[mid] = ["local"]

        if self._cap_available:
            try:
                import cap

                for mid in cap.list_metrics():
                    result.setdefault(mid, []).append("cap")
            except (AttributeError, TypeError):
                pass

        return result
