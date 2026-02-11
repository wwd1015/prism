"""Tests for prism.core — Report class and pre-compute orchestration."""

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml
from openpyxl import Workbook

from prism.core import Report, load_model_config


@pytest.fixture
def sample_config():
    return {
        "model_id": "test_model",
        "model_name": "Test Model",
        "model_version": "1.0.0",
        "primary_model_developer": "team-test",
        "model_repo_url": "https://github.com/example/test-model",
        "metrics": {
            "rank_ordering": {
                "sector": "discriminatory_power",
                "metric_id": "gini_coefficient",
                "source": "local",
                "inputs": {"segment": "all"},
                "color_field": "gini_value",
                "color": {
                    "green": ">= 0.4",
                    "yellow": ">= 0.3",
                    "red": "< 0.3",
                },
            },
            "accuracy": {
                "sector": "discriminatory_power",
                "metric_id": "model_accuracy",
                "source": "local",
                "inputs": {"method": "auc"},
                "color_field": "auc_value",
                "color": {
                    "green": ">= 0.85",
                    "yellow": ">= 0.75",
                    "red": "< 0.75",
                },
            },
        },
        "aggregation": {
            "sector": {"method": "worst_color"},
            "final": {"method": "worst_color"},
        },
    }


@pytest.fixture
def config_dir(sample_config, tmp_path):
    models_dir = tmp_path / "config" / "models"
    models_dir.mkdir(parents=True)
    config_path = models_dir / "test_model.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return tmp_path / "config"


@pytest.fixture
def sample_data():
    """Create a sample DataFrame with clear separation."""
    import numpy as np

    np.random.seed(42)
    n = 200
    actuals = np.array([1] * 100 + [0] * 100)
    # Good model: higher scores for actuals=1
    predicted = np.where(actuals == 1, np.random.beta(5, 2, n), np.random.beta(2, 5, n))
    return pd.DataFrame({"actual": actuals, "predicted": predicted})


class TestLoadModelConfig:
    def test_load_existing(self, config_dir):
        cfg = load_model_config(config_dir, "test_model")
        assert cfg["model_id"] == "test_model"
        assert "metrics" in cfg

    def test_load_missing_raises(self, config_dir):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_model_config(config_dir, "nonexistent")


class TestReport:
    def test_init(self, config_dir):
        r = Report("test_model", config_dir=str(config_dir))
        assert r.model_id == "test_model"
        assert r.model_name == "Test Model"
        assert r._computed is False

    def test_compute_all(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        assert r._computed is True

    def test_metric_before_compute_raises(self, config_dir):
        r = Report("test_model", config_dir=str(config_dir))
        with pytest.raises(RuntimeError, match="compute_all"):
            r.metric("rank_ordering")

    def test_metric_after_compute(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        result = r.metric("rank_ordering")
        assert "gini_value" in result

    def test_metric_value(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        val = r.metric_value("rank_ordering")
        assert isinstance(val, float)

    def test_metric_color(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        color = r.metric_color("rank_ordering")
        assert color in ("green", "yellow", "red")

    def test_sector_colors(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        sc = r.sector_colors()
        assert "discriminatory_power" in sc
        assert sc["discriminatory_power"] in ("green", "yellow", "red")

    def test_final_color(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        assert r.final_color() in ("green", "yellow", "red")

    def test_scorecard(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        sc = r.scorecard()
        assert "Rank Ordering" in sc
        assert "Accuracy" in sc
        assert "Overall Model Rating" in sc

    def test_header(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        header = r.header()
        assert "Test Model" in header

    def test_section_header(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        sh = r.section_header("rank_ordering")
        assert "Rank Ordering" in sh

    def test_badge(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        badge = r.badge("green")
        assert "Green" in badge
        assert "#28a745" in badge

    def test_table(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        result = r.metric("rank_ordering")
        table = r.table(result["summary"])
        assert "decile" in table

    def test_missing_metric_key_raises(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)
        with pytest.raises(KeyError, match="not found"):
            r.metric("nonexistent_metric")


def _create_commentary_xlsx(path, model_id, rows):
    """Helper to create a commentary Excel file for tests."""
    wb = Workbook()
    ws = wb.active
    ws.title = model_id
    headers = ["metric_key", "commentary", "author", "date"]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    wb.save(path)


class TestCommentary:
    def test_loads_commentary(self, config_dir, sample_data, tmp_path):
        xlsx = tmp_path / "commentary.xlsx"
        _create_commentary_xlsx(xlsx, "test_model", [
            {"metric_key": "rank_ordering", "commentary": "Gini looks fine.", "author": "J. Smith", "date": "2025-01-15"},
            {"metric_key": "accuracy", "commentary": "AUC within tolerance.", "author": "A. Lee"},
        ])
        r = Report("test_model", config_dir=str(config_dir), commentary_file=str(xlsx))
        r.compute_all(data=sample_data)

        c = r.commentary("rank_ordering")
        assert "Gini looks fine." in c
        assert "J. Smith" in c
        assert "2025-01-15" in c
        assert ":::{.callout-note" in c

    def test_commentary_with_author_no_date(self, config_dir, sample_data, tmp_path):
        xlsx = tmp_path / "commentary.xlsx"
        _create_commentary_xlsx(xlsx, "test_model", [
            {"metric_key": "accuracy", "commentary": "AUC within tolerance.", "author": "A. Lee"},
        ])
        r = Report("test_model", config_dir=str(config_dir), commentary_file=str(xlsx))
        r.compute_all(data=sample_data)

        c = r.commentary("accuracy")
        assert "AUC within tolerance." in c
        assert "A. Lee" in c

    def test_no_commentary_returns_empty(self, config_dir, sample_data, tmp_path):
        xlsx = tmp_path / "commentary.xlsx"
        _create_commentary_xlsx(xlsx, "test_model", [
            {"metric_key": "rank_ordering", "commentary": "Some note."},
        ])
        r = Report("test_model", config_dir=str(config_dir), commentary_file=str(xlsx))
        r.compute_all(data=sample_data)

        # No commentary for accuracy
        assert r.commentary("accuracy") == ""

    def test_missing_tab_graceful(self, config_dir, sample_data, tmp_path):
        xlsx = tmp_path / "commentary.xlsx"
        # Create with a different model_id tab
        _create_commentary_xlsx(xlsx, "other_model", [
            {"metric_key": "rank_ordering", "commentary": "Note."},
        ])
        r = Report("test_model", config_dir=str(config_dir), commentary_file=str(xlsx))
        r.compute_all(data=sample_data)

        assert r.commentary("rank_ordering") == ""

    def test_missing_file_graceful(self, config_dir, sample_data, tmp_path):
        xlsx = tmp_path / "nonexistent.xlsx"
        r = Report("test_model", config_dir=str(config_dir), commentary_file=str(xlsx))
        r.compute_all(data=sample_data)

        assert r.commentary("rank_ordering") == ""

    def test_no_commentary_file(self, config_dir, sample_data):
        r = Report("test_model", config_dir=str(config_dir))
        r.compute_all(data=sample_data)

        # Should return empty string, no errors
        assert r.commentary("rank_ordering") == ""
