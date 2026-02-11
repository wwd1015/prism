"""Tests for prism.colors — RAG color evaluation and aggregation."""

import pytest

from prism.colors import (
    aggregate_matrix_rules,
    aggregate_sector,
    compute_all_colors,
    evaluate_color,
    parse_matrix_rules,
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
                    "rules": [
                        "green  | green  = green",
                        "green  | yellow = yellow",
                        "green  | red    = red",
                        "yellow | green  = yellow",
                        "yellow | yellow = yellow",
                        "yellow | red    = red",
                        "red    | *      = red",
                    ],
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


# --- parse_matrix_rules ---


class TestParseMatrixRules:
    def test_basic_parse(self):
        rules = ["green | green = green", "green | red = red"]
        parsed = parse_matrix_rules(rules, 2)
        assert parsed[("green", "green")] == "green"
        assert parsed[("green", "red")] == "red"

    def test_wildcard(self):
        rules = ["red | * = red"]
        parsed = parse_matrix_rules(rules, 2)
        assert parsed[("red", "*")] == "red"

    def test_three_dimensions(self):
        rules = ["green | yellow | red = red"]
        parsed = parse_matrix_rules(rules, 3)
        assert parsed[("green", "yellow", "red")] == "red"

    def test_dimension_mismatch(self):
        with pytest.raises(ValueError, match="2 dimensions, expected 3"):
            parse_matrix_rules(["green | red = red"], 3)

    def test_invalid_color(self):
        with pytest.raises(ValueError, match="Invalid color"):
            parse_matrix_rules(["green | blue = red"], 2)

    def test_invalid_result(self):
        with pytest.raises(ValueError, match="Invalid result color"):
            parse_matrix_rules(["green | green = blue"], 2)

    def test_missing_equals(self):
        with pytest.raises(ValueError, match="missing '='"):
            parse_matrix_rules(["green | green green"], 2)


# --- aggregate_matrix_rules ---


class TestAggregateMatrixRules:
    def test_exact_match(self):
        rules = {("green", "yellow"): "yellow", ("green", "green"): "green"}
        assert aggregate_matrix_rules({"a": "green", "b": "yellow"}, ["a", "b"], rules) == "yellow"

    def test_wildcard_fallback(self):
        rules = {("red", "*"): "red"}
        assert aggregate_matrix_rules({"a": "red", "b": "green"}, ["a", "b"], rules) == "red"

    def test_exact_before_wildcard(self):
        rules = {("red", "green"): "yellow", ("red", "*"): "red"}
        assert aggregate_matrix_rules({"a": "red", "b": "green"}, ["a", "b"], rules) == "yellow"

    def test_catch_all(self):
        rules = {("*", "*"): "yellow"}
        assert aggregate_matrix_rules({"a": "red", "b": "green"}, ["a", "b"], rules) == "yellow"

    def test_no_match_raises(self):
        rules = {("green", "green"): "green"}
        with pytest.raises(KeyError, match="No rule matched"):
            aggregate_matrix_rules({"a": "red", "b": "red"}, ["a", "b"], rules)

    def test_three_dim_wildcard(self):
        rules = {("red", "*", "*"): "red", ("green", "green", "green"): "green"}
        assert aggregate_matrix_rules(
            {"a": "red", "b": "yellow", "c": "green"}, ["a", "b", "c"], rules
        ) == "red"


# --- compute_all_colors with rules ---


class TestComputeAllColorsRules:
    def test_rules_format_end_to_end(self):
        config = {
            "metrics": {
                "gini": {
                    "sector": "disc_power",
                    "color": {"green": ">= 0.4", "yellow": ">= 0.3", "red": "< 0.3"},
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
                    "rules": [
                        "green  | green  = green",
                        "green  | yellow = yellow",
                        "yellow | green  = yellow",
                        "yellow | yellow = yellow",
                        "*      | red    = red",
                        "red    | *      = red",
                    ],
                },
            },
        }
        result = compute_all_colors(config, {"gini": 0.5, "psi": 0.05})
        assert result["final"] == "green"

        result2 = compute_all_colors(config, {"gini": 0.5, "psi": 0.30})
        assert result2["final"] == "red"

