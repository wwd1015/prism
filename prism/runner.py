"""Quarto rendering orchestration.

Handles rendering individual model reports and batch rendering
all configured models. Requires the Quarto CLI on PATH.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _find_quarto() -> str:
    """Locate the quarto executable."""
    quarto = shutil.which("quarto")
    if quarto is None:
        raise RuntimeError(
            "Quarto CLI not found on PATH. "
            "Install it from https://quarto.org/docs/get-started/"
        )
    return quarto


def _find_report_qmd(model_id: str, reports_dir: str = "reports") -> Path:
    """Find the .qmd report file for a given model."""
    base = Path(reports_dir) / model_id
    if not base.is_dir():
        raise FileNotFoundError(f"Report directory not found: {base}")
    qmd_files = list(base.glob("*.qmd"))
    if not qmd_files:
        raise FileNotFoundError(f"No .qmd files found in {base}")
    return qmd_files[0]


def render_report(
    model_id: str,
    format: str | None = None,
    output_dir: str = "_output",
    report_date: str | None = None,
    reports_dir: str = "reports",
) -> Path:
    """Render a single model's report via Quarto.

    Args:
        model_id: The model identifier.
        format: Output format ("html", "pdf", "revealjs"). If None, uses
            all formats defined in the .qmd front matter.
        output_dir: Base output directory.
        report_date: Report date parameter. Defaults to today.
        reports_dir: Directory containing per-model report folders.

    Returns:
        Path to the output directory for this model.
    """
    from datetime import date

    quarto = _find_quarto()
    qmd_path = _find_report_qmd(model_id, reports_dir)

    report_date = report_date or date.today().isoformat()
    model_output = Path(output_dir) / model_id
    model_output.mkdir(parents=True, exist_ok=True)

    cmd = [
        quarto,
        "render",
        str(qmd_path),
        "--output-dir",
        str(model_output.resolve()),
        "-P",
        f"model_id:{model_id}",
        "-P",
        f"report_date:{report_date}",
    ]
    if format:
        cmd.extend(["--to", format])

    logger.info(f"Rendering {model_id}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"Quarto render failed for {model_id}:\n{result.stderr}")
        raise RuntimeError(
            f"Quarto render failed for {model_id}. "
            f"Exit code: {result.returncode}\n{result.stderr}"
        )

    logger.info(f"Successfully rendered {model_id} → {model_output}")
    return model_output


def _load_project_config(config_dir: str = "config") -> dict:
    """Load the project-level config (config/project.yaml)."""
    path = Path(config_dir) / "project.yaml"
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def list_models(config_dir: str = "config") -> list[dict]:
    """List all configured model IDs from the config/models/ directory.

    Returns:
        List of dicts with model_id, model_name, and tags.
    """
    models_dir = Path(config_dir) / "models"
    if not models_dir.is_dir():
        return []

    result = []
    for yaml_file in sorted(models_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            cfg = yaml.safe_load(f) or {}
        result.append(
            {
                "model_id": cfg.get("model_id", yaml_file.stem),
                "model_name": cfg.get("model_name", yaml_file.stem),
                "model_version": cfg.get("model_version"),
                "tags": cfg.get("tags", []),
            }
        )
    return result


def render_all(
    tag: str | None = None,
    format: str | None = None,
    config_dir: str = "config",
    output_dir: str = "_output",
    report_date: str | None = None,
    reports_dir: str = "reports",
) -> list[dict]:
    """Batch render all (or tagged) model reports.

    Args:
        tag: If set, only render models with this tag.
        format: Output format (or None for all formats).
        config_dir: Path to the config directory.
        output_dir: Base output directory.
        report_date: Report date parameter.
        reports_dir: Directory containing per-model report folders.

    Returns:
        List of dicts with model_id and status ("success" or error message).
    """
    models = list_models(config_dir)
    if tag:
        models = [m for m in models if tag in m.get("tags", [])]

    results = []
    for m in models:
        model_id = m["model_id"]
        try:
            render_report(
                model_id,
                format=format,
                output_dir=output_dir,
                report_date=report_date,
                reports_dir=reports_dir,
            )
            results.append({"model_id": model_id, "status": "success"})
            logger.info(f"[OK] {model_id}")
        except Exception as e:
            results.append({"model_id": model_id, "status": str(e)})
            logger.error(f"[FAIL] {model_id}: {e}")

    return results
