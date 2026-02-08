"""Local metric registry with decorator-based registration.

Metrics register themselves at import time using the @register_metric
decorator. The resolver then looks up metrics from this registry.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}


def register_metric(metric_id: str) -> Callable:
    """Decorator to register a local metric function.

    Args:
        metric_id: Unique identifier for the metric (e.g. "gini_coefficient").

    Usage:
        @register_metric("gini_coefficient")
        def gini_coefficient(data, **kwargs):
            ...
    """

    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        if metric_id in _REGISTRY:
            raise ValueError(
                f"Metric {metric_id!r} is already registered "
                f"(existing: {_REGISTRY[metric_id].__module__}.{_REGISTRY[metric_id].__name__})"
            )
        _REGISTRY[metric_id] = fn
        return fn

    return decorator


def get_metric(metric_id: str) -> Callable[..., dict[str, Any]] | None:
    """Look up a registered metric function by ID."""
    return _REGISTRY.get(metric_id)


def list_metrics() -> list[str]:
    """Return all registered metric IDs."""
    return list(_REGISTRY.keys())
