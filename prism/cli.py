"""Click CLI for PRISM.

Commands:
  prism init <project-name>       Create new report project from templates
  prism add-model <model_id>      Add a new model config + report .qmd
  prism render <model_id>         Render one model's report
  prism render-all                Render all models
  prism list                      List all configured models
  prism validate                  Validate all YAML configs
  prism preview <model_id>        Quick HTML preview, open in browser
"""

from __future__ import annotations

import shutil
import webbrowser
from importlib import resources
from pathlib import Path

import click
import yaml


@click.group()
@click.version_option(package_name="prism")
def cli():
    """PRISM — Performance Reporting & Insight for Standardized Monitoring."""


@cli.command()
@click.argument("project_name")
def init(project_name: str):
    """Create a new report project from built-in templates."""
    dest = Path(project_name)
    if dest.exists():
        raise click.ClickException(f"Directory {project_name!r} already exists.")

    # Copy template directory
    templates_dir = resources.files("prism") / "templates"
    shutil.copytree(str(templates_dir), str(dest))

    click.echo(f"Created project: {dest.resolve()}")
    click.echo(f"  config/    — model configuration YAML files")
    click.echo(f"  _common/   — shared report sections (.qmd)")
    click.echo(f"  reports/   — per-model report files (.qmd)")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  cd {project_name}")
    click.echo(f"  prism render example_model")


@cli.command("add-model")
@click.argument("model_id")
def add_model(model_id: str):
    """Add a new model configuration and report .qmd file."""
    config_dir = Path("config") / "models"
    reports_dir = Path("reports") / model_id

    if not config_dir.exists():
        raise click.ClickException(
            "Not in a PRISM project directory. Run 'prism init' first."
        )

    # Create config YAML
    config_path = config_dir / f"{model_id}.yaml"
    if config_path.exists():
        raise click.ClickException(f"Config already exists: {config_path}")

    config = {
        "model_id": model_id,
        "model_name": model_id.replace("_", " ").title(),
        "model_version": "1.0.0",
        "primary_model_developer": "developer-name",
        "model_repo_url": "",
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
        },
        "aggregation": {
            "sector": {"method": "worst_color"},
            "final": {"method": "worst_color"},
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    click.echo(f"Created config: {config_path}")

    # Create report .qmd
    reports_dir.mkdir(parents=True, exist_ok=True)
    qmd_path = reports_dir / "monitoring.qmd"
    qmd_content = f"""---
title: "Model Monitoring Report"
params:
  model_id: "{model_id}"
  report_date: ""
format:
  html:
    toc: true
    theme: cosmo
---

{{{{< include ../../_common/setup.qmd >}}}}
{{{{< include ../../_common/header.qmd >}}}}
{{{{< include ../../_common/scorecard.qmd >}}}}
{{{{< include ../../_common/rank_ordering.qmd >}}}}
{{{{< include ../../_common/footer.qmd >}}}}
"""
    with open(qmd_path, "w") as f:
        f.write(qmd_content)
    click.echo(f"Created report: {qmd_path}")


@cli.command()
@click.argument("model_id")
@click.option("--format", "fmt", default=None, help="Output format: html, pdf, revealjs")
@click.option("--output-dir", default="_output", help="Output directory")
@click.option("--date", "report_date", default=None, help="Report date (YYYY-MM-DD)")
def render(model_id: str, fmt: str | None, output_dir: str, report_date: str | None):
    """Render a single model's report."""
    from prism.runner import render_report

    try:
        out = render_report(
            model_id, format=fmt, output_dir=output_dir, report_date=report_date
        )
        click.echo(f"Rendered {model_id} → {out}")
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command("render-all")
@click.option("--tag", default=None, help="Only render models with this tag")
@click.option("--format", "fmt", default=None, help="Output format: html, pdf, revealjs")
@click.option("--output-dir", default="_output", help="Output directory")
@click.option("--date", "report_date", default=None, help="Report date (YYYY-MM-DD)")
def render_all_cmd(
    tag: str | None, fmt: str | None, output_dir: str, report_date: str | None
):
    """Render all configured model reports."""
    from prism.runner import render_all

    results = render_all(
        tag=tag, format=fmt, output_dir=output_dir, report_date=report_date
    )
    for r in results:
        status = "OK" if r["status"] == "success" else f'FAIL: {r["status"]}'
        click.echo(f"  [{status}] {r['model_id']}")

    successes = sum(1 for r in results if r["status"] == "success")
    click.echo(f"\n{successes}/{len(results)} models rendered successfully.")


@cli.command("list")
def list_cmd():
    """List all configured models."""
    from prism.runner import list_models

    models = list_models()
    if not models:
        click.echo("No models configured. Run 'prism add-model <model_id>' to add one.")
        return

    click.echo(f"{'Model ID':<25} {'Name':<35} {'Tags'}")
    click.echo("-" * 80)
    for m in models:
        tags = ", ".join(m.get("tags", [])) or "—"
        click.echo(f"{m['model_id']:<25} {m['model_name']:<35} {tags}")


@cli.command()
def validate():
    """Validate all YAML model configurations."""
    config_dir = Path("config") / "models"
    if not config_dir.is_dir():
        raise click.ClickException("config/models/ directory not found.")

    errors = []
    for yaml_file in sorted(config_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                cfg = yaml.safe_load(f)
            # Basic validation
            if not isinstance(cfg, dict):
                errors.append((yaml_file.name, "File does not contain a YAML mapping"))
                continue
            if "model_id" not in cfg:
                errors.append((yaml_file.name, "Missing 'model_id' field"))
            if "metrics" not in cfg:
                errors.append((yaml_file.name, "Missing 'metrics' field"))
            else:
                for key, mcfg in cfg["metrics"].items():
                    if "metric_id" not in mcfg:
                        errors.append((yaml_file.name, f"Metric {key!r}: missing 'metric_id'"))
                    if "color" not in mcfg:
                        errors.append((yaml_file.name, f"Metric {key!r}: missing 'color' thresholds"))

            click.echo(f"  [OK] {yaml_file.name}")
        except yaml.YAMLError as e:
            errors.append((yaml_file.name, f"YAML parse error: {e}"))

    if errors:
        click.echo(f"\nFound {len(errors)} error(s):")
        for fname, msg in errors:
            click.echo(f"  {fname}: {msg}")
        raise SystemExit(1)
    else:
        click.echo("\nAll configs valid.")


@cli.command()
@click.argument("model_id")
@click.option("--date", "report_date", default=None, help="Report date (YYYY-MM-DD)")
def preview(model_id: str, report_date: str | None):
    """Render HTML and open in browser for quick preview."""
    from prism.runner import render_report

    try:
        out = render_report(
            model_id, format="html", output_dir="_output", report_date=report_date
        )
        html_files = list(out.glob("*.html"))
        if html_files:
            url = html_files[0].resolve().as_uri()
            click.echo(f"Opening {url}")
            webbrowser.open(url)
        else:
            click.echo(f"Rendered to {out} but no HTML file found.")
    except Exception as e:
        raise click.ClickException(str(e))
