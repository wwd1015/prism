"""Tests for prism.helpers — formatting helper functions."""

import pandas as pd
import pytest

from prism.helpers import (
    format_badge,
    format_commentary,
    format_delta,
    format_kpi,
    format_scorecard,
    format_table,
    version_match_semver,
)


class TestFormatTable:
    def test_basic_dataframe(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.1234567, 5.9876543, 6.0]})
        result = format_table(df)
        assert "a" in result
        assert "b" in result
        # Floats should be rounded to 4 decimal places
        assert "4.1235" in result

    def test_max_rows_truncation(self):
        df = pd.DataFrame({"x": range(100)})
        result = format_table(df, max_rows=10)
        assert "Showing 10 of 100 rows" in result

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = format_table(df)
        assert isinstance(result, str)


class TestFormatBadge:
    def test_green(self):
        result = format_badge("green")
        assert "Green" in result
        assert "#28a745" in result

    def test_yellow(self):
        result = format_badge("yellow")
        assert "Yellow" in result
        assert "#ffc107" in result

    def test_red(self):
        result = format_badge("red")
        assert "Red" in result
        assert "#dc3545" in result

    def test_custom_label(self):
        result = format_badge("green", label="Pass")
        assert "Pass" in result
        assert "Green" not in result

    def test_unknown_color_defaults_to_red_style(self):
        result = format_badge("purple")
        assert "#dc3545" in result


class TestFormatKpi:
    def test_plain(self):
        result = format_kpi("Score", 0.95)
        assert "Score" in result
        assert "0.95" in result

    def test_with_color(self):
        result = format_kpi("Score", 0.95, color="green")
        assert "#28a745" in result

    def test_with_format(self):
        result = format_kpi("Accuracy", 0.9512, fmt=".2%")
        assert "95.12%" in result


class TestFormatScorecard:
    def test_basic_scorecard(self):
        metrics_data = [
            {"key": "gini", "name": "Gini", "sector": "disc_power", "value": 0.45, "color": "green"},
            {"key": "auc", "name": "AUC", "sector": "disc_power", "value": 0.80, "color": "yellow"},
            {"key": "psi", "name": "PSI", "sector": "stability", "value": 0.05, "color": "green"},
        ]
        sector_colors = {"disc_power": "yellow", "stability": "green"}
        result = format_scorecard(metrics_data, sector_colors, "yellow")

        assert "Gini" in result
        assert "AUC" in result
        assert "PSI" in result
        assert "Overall Model Rating" in result

    def test_no_value(self):
        metrics_data = [
            {"key": "m1", "name": "M1", "sector": "s1", "value": None, "color": "green"},
        ]
        result = format_scorecard(metrics_data, {"s1": "green"}, "green")
        # None value should show as dash
        assert "\u2014" in result  # em-dash


class TestFormatCommentary:
    def test_basic(self):
        result = format_commentary("Gini dropped due to portfolio shift.")
        assert ":::{.callout-note" in result
        assert "Gini dropped due to portfolio shift." in result
        assert ":::" in result

    def test_with_author(self):
        result = format_commentary("Looks good.", author="J. Smith")
        assert "J. Smith" in result

    def test_with_author_and_date(self):
        result = format_commentary("No action.", author="A. Lee", date="2025-01-15")
        assert "A. Lee" in result
        assert "2025-01-15" in result

    def test_no_attribution(self):
        result = format_commentary("Just a note.")
        # Should not contain attribution line
        assert "*—" not in result


class TestFormatDelta:
    def test_positive_pct(self):
        result = format_delta(1.1, 1.0)
        assert "\u25b2" in result  # up arrow
        assert "+10.0%" in result

    def test_negative_pct(self):
        result = format_delta(0.9, 1.0)
        assert "\u25bc" in result  # down arrow
        assert "-10.0%" in result

    def test_absolute(self):
        result = format_delta(1.5, 1.0, fmt="abs")
        assert "\u25b2" in result
        assert "+0.5000" in result

    def test_zero_previous_uses_abs(self):
        result = format_delta(0.5, 0.0, fmt="pct")
        # Division by zero fallback → uses absolute
        assert "\u25b2" in result


class TestVersionMatchSemver:
    def test_exact_match(self):
        assert version_match_semver("2.1.0", "2.1.0") is True

    def test_exact_mismatch(self):
        assert version_match_semver("2.1.0", "2.2.0") is False

    def test_wildcard_minor_patch(self):
        assert version_match_semver("3.5.2", "3.x.x") is True

    def test_wildcard_patch_only(self):
        assert version_match_semver("1.2.9", "1.2.x") is True

    def test_wildcard_mismatch(self):
        assert version_match_semver("2.1.0", "3.x.x") is False

    def test_all_wildcards(self):
        assert version_match_semver("9.9.9", "x.x.x") is True

    def test_invalid_version_too_few_parts(self):
        with pytest.raises(ValueError, match="Invalid semver version"):
            version_match_semver("2.1", "2.1.0")

    def test_invalid_pattern_too_many_parts(self):
        with pytest.raises(ValueError, match="Invalid semver pattern"):
            version_match_semver("2.1.0", "2.1.0.0")
