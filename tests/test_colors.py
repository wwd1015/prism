"""Tests for prism.colors — RAG color evaluation and aggregation."""

import pytest

from prism.colors import (
    aggregate_matrix,
    aggregate_sector,
    compute_all_colors,
    evaluate_color,
    parse_threshold,
)


# --- parse_threshold ---


class TestParseThreshold:
    def test_gte(self):
        pred = parse_threshold(">= 0.4")
        assert pred(0.4) is True
        assert pred(0.5) is True
        assert pred(0.39) is False

    def test_lt(self):
        pred = parse_threshold("< 0.3")
        assert pred(0.29) is True
        assert pred(0.3) is False
        assert pred(0.31) is False

    def test_lte(self):
        pred = parse_threshold("<= 100")
        assert pred(100) is True
        assert pred(99) is True
        assert pred(101) is False

    def test_gt(self):
        pred = parse_threshold("> 0")
        assert pred(1) is True
        assert pred(0) is False

    def test_eq(self):
        pred = parse_threshold("== 1.0")
        assert pred(1.0) is True
        assert pred(1.1) is False

    def test_negative_value(self):
        pred = parse_threshold(">= -0.5")
        assert pred(-0.5) is True
        assert pred(-0.6) is False

    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="Invalid threshold"):
            parse_threshold("around 0.5")

    def test_whitespace(self):
        pred = parse_threshold("  >= 0.4  ")
        assert pred(0.4) is True


# --- evaluate_color ---


class TestEvaluateColor:
    def test_green(self):
        thresholds = {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"}
        assert evaluate_color(0.5, thresholds) == "green"

    def test_yellow(self):
        thresholds = {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"}
        assert evaluate_color(0.35, thresholds) == "yellow"

    def test_red(self):
        thresholds = {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"}
        assert evaluate_color(0.1, thresholds) == "red"

    def test_boundary_green(self):
        thresholds = {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"}
        assert evaluate_color(0.4, thresholds) == "green"

    def test_boundary_yellow(self):
        thresholds = {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"}
        assert evaluate_color(0.3, thresholds) == "yellow"

    def test_lower_is_better(self):
        # PSI-style: lower values are better
        thresholds = {"green": "< 0.1", "yellow": "< 0.25", "red": ">= 0.25"}
        assert evaluate_color(0.05, thresholds) == "green"
        assert evaluate_color(0.15, thresholds) == "yellow"
        assert evaluate_color(0.30, thresholds) == "red"

    def test_no_match_raises(self):
        # Intentionally broken thresholds
        thresholds = {"green": "> 100", "yellow": "> 200"}
        with pytest.raises(ValueError, match="No threshold matched"):
            evaluate_color(50, thresholds)


# --- aggregate_sector ---


class TestAggregateSector:
    def test_worst_color_all_green(self):
        assert aggregate_sector(["green", "green", "green"]) == "green"

    def test_worst_color_mixed(self):
        assert aggregate_sector(["green", "yellow", "green"]) == "yellow"

    def test_worst_color_with_red(self):
        assert aggregate_sector(["green", "yellow", "red"]) == "red"

    def test_best_color(self):
        assert aggregate_sector(["red", "yellow", "green"], "best_color") == "green"

    def test_best_color_no_green(self):
        assert aggregate_sector(["red", "yellow"], "best_color") == "yellow"

    def test_majority_clear(self):
        assert aggregate_sector(["green", "green", "red"], "majority") == "green"

    def test_majority_tie_breaks_worst(self):
        # green=1, yellow=1 → tie → worst (yellow) wins
        assert aggregate_sector(["green", "yellow"], "majority") == "yellow"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            aggregate_sector([])

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            aggregate_sector(["green"], "median")


# --- aggregate_matrix ---


class TestAggregateMatrix:
    MATRIX = {
        "green": {"green": "green", "yellow": "yellow", "red": "red"},
        "yellow": {"green": "yellow", "yellow": "yellow", "red": "red"},
        "red": {"green": "red", "yellow": "red", "red": "red"},
    }

    def test_all_green(self):
        sector_colors = {"a": "green", "b": "green", "c": "green"}
        assert aggregate_matrix(sector_colors, ["a", "b", "c"], self.MATRIX) == "green"

    def test_one_yellow(self):
        sector_colors = {"a": "green", "b": "yellow"}
        assert aggregate_matrix(sector_colors, ["a", "b"], self.MATRIX) == "yellow"

    def test_red_dominates(self):
        sector_colors = {"a": "green", "b": "red", "c": "green"}
        # green × red → red, red × green → red
        assert aggregate_matrix(sector_colors, ["a", "b", "c"], self.MATRIX) == "red"

    def test_three_dimensions(self):
        sector_colors = {"a": "green", "b": "yellow", "c": "yellow"}
        # green × yellow → yellow, yellow × yellow → yellow
        assert aggregate_matrix(sector_colors, ["a", "b", "c"], self.MATRIX) == "yellow"

    def test_too_few_dimensions(self):
        with pytest.raises(ValueError, match="at least 2"):
            aggregate_matrix({"a": "green"}, ["a"], self.MATRIX)


# --- compute_all_colors ---


class TestComputeAllColors:
    def test_full_pipeline(self):
        config = {
            "metrics": {
                "gini": {
                    "sector": "disc_power",
                    "color": {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"},
                },
                "auc": {
                    "sector": "disc_power",
                    "color": {"green": ">= 0.85", "yellow": ">= 0.75", "red": "< 0.75"},
                },
                "psi": {
                    "sector": "stability",
                    "color": {"green": "< 0.1", "yellow": "< 0.25", "red": ">= 0.25"},
                },
            },
            "aggregation": {
                "sector": {"method": "worst_color"},
                "final": {
                    "method": "matrix",
                    "dimensions": ["disc_power", "stability"],
                    "matrix": {
                        "green": {"green": "green", "yellow": "yellow", "red": "red"},
                        "yellow": {"green": "yellow", "yellow": "yellow", "red": "red"},
                        "red": {"green": "red", "yellow": "red", "red": "red"},
                    },
                },
            },
        }
        metric_values = {"gini": 0.5, "auc": 0.80, "psi": 0.05}
        result = compute_all_colors(config, metric_values)

        assert result["metrics"]["gini"] == "green"
        assert result["metrics"]["auc"] == "yellow"
        assert result["metrics"]["psi"] == "green"
        # disc_power: worst(green, yellow) = yellow
        assert result["sectors"]["disc_power"] == "yellow"
        # stability: worst(green) = green
        assert result["sectors"]["stability"] == "green"
        # matrix: yellow × green → yellow
        assert result["final"] == "yellow"

    def test_no_aggregation_config(self):
        config = {
            "metrics": {
                "m1": {
                    "sector": "s1",
                    "color": {"green": ">= 0.5", "yellow": ">= 0.3", "red": "< 0.3"},
                },
            },
        }
        result = compute_all_colors(config, {"m1": 0.6})
        assert result["metrics"]["m1"] == "green"
        assert result["sectors"]["s1"] == "green"
        assert result["final"] == "green"

    def test_missing_metric_value_skipped(self):
        config = {
            "metrics": {
                "m1": {
                    "sector": "s1",
                    "color": {"green": ">= 0.5", "red": "< 0.5"},
                },
            },
        }
        result = compute_all_colors(config, {})
        assert result["metrics"] == {}
