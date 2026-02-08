"""Tests for prism.resolver — metric resolution (local vs CAP)."""

import warnings

import pandas as pd
import pytest

from prism.resolver import MetricResolver


@pytest.fixture
def resolver():
    return MetricResolver()


class TestMetricResolver:
    def test_call_local_gini(self, resolver):
        """Local gini_coefficient should be callable."""
        df = pd.DataFrame(
            {"actual": [1, 0, 1, 0, 1, 0, 0, 1, 0, 0], "predicted": [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.4, 0.6, 0.35, 0.15]}
        )
        result = resolver.call("gini_coefficient", source="local", data=df)
        assert "gini_value" in result
        assert isinstance(result["gini_value"], float)

    def test_call_local_psi(self, resolver):
        """Local psi_calculator should be callable."""
        df = pd.DataFrame(
            {
                "predicted": [0.1, 0.2, 0.3, 0.4, 0.5] * 20,
                "reference_score": [0.15, 0.25, 0.35, 0.45, 0.55] * 20,
            }
        )
        result = resolver.call("psi_calculator", source="local", data=df)
        assert "psi_value" in result
        assert isinstance(result["psi_value"], float)

    def test_call_local_model_accuracy(self, resolver):
        """Local model_accuracy should be callable."""
        df = pd.DataFrame(
            {"actual": [1, 0, 1, 0, 1, 0, 0, 1, 0, 0], "predicted": [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.4, 0.6, 0.35, 0.15]}
        )
        result = resolver.call("model_accuracy", source="local", data=df, method="auc")
        assert "auc_value" in result
        assert 0 <= result["auc_value"] <= 1

    def test_unknown_metric_raises(self, resolver):
        with pytest.raises(ValueError, match="not found"):
            resolver.call("nonexistent_metric", source="local")

    def test_cap_fallback_warns(self, resolver, monkeypatch):
        """When source='cap' but CAP not installed, should warn and fall back."""
        # Force CAP to appear unavailable
        monkeypatch.setattr(resolver, "_cap_available", False)

        df = pd.DataFrame(
            {"actual": [1, 0, 1, 0], "predicted": [0.9, 0.1, 0.8, 0.2]}
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = resolver.call(
                "gini_coefficient", source="cap", data=df
            )
            assert len(w) == 1
            assert "CAP is not installed" in str(w[0].message)
            assert "gini_value" in result

    def test_available_metrics(self, resolver):
        available = resolver.available_metrics()
        assert "gini_coefficient" in available
        assert "local" in available["gini_coefficient"]
        assert "psi_calculator" in available
        assert "model_accuracy" in available
