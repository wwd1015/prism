# PRISM — Performance Reporting & Insight for Standardized Monitoring

## What This Project Is

PRISM is a Python package that generates shareable model monitoring reports (HTML, PDF, slides) using Quarto as the rendering engine. It provides a RAG (Red/Amber/Green) color system with multi-layer aggregation for model health assessment.

**Primary use case**: Model monitoring reports where each model has its own `.qmd` report file, shares common metric sections (rank ordering, accuracy, etc.), and uses a RAG color system with multi-layer aggregation (metrics → sector ratings → final model color via mapping matrix).

**CAP integration**: PRISM works standalone with built-in metric functions. CAP (Commercial Analytical Platform) is an optional backend that can be swapped in later by changing `source: local` to `source: cap` in model YAML configs.

## Architecture

- **Two-phase execution**: `Report.compute_all()` pre-computes ALL metrics+colors in `setup.qmd` before any rendering begins. This solves the scorecard-at-top problem (scorecard needs all metric results but appears first in the report).
- **Metric resolver**: `resolver.py` abstracts metric source — routes to local functions or CAP without changing report code.
- **Color pipeline**: Individual metric thresholds → sector aggregation (worst_color/best_color/majority) → final model color via mapping matrix.

## Package Structure

```
prism/
├── __init__.py          # Public API: Report, MetricResolver, evaluate_color, format_badge, format_table
├── core.py              # Report class — config loading, compute_all(), cached accessors, rendering helpers
├── resolver.py          # MetricResolver — routes to local or CAP backend
├── colors.py            # RAG thresholds, sector aggregation, matrix aggregation, compute_all_colors
├── helpers.py           # format_table, format_badge, format_kpi, format_scorecard, format_delta
├── runner.py            # Quarto rendering orchestration (single + batch)
├── cli.py               # Click CLI: init, add-model, render, render-all, list, validate, preview
├── metrics/
│   ├── registry.py      # @register_metric decorator + global registry
│   ├── rank_ordering.py # gini_coefficient, ks_statistic
│   ├── accuracy.py      # model_accuracy, precision_recall
│   └── stability.py     # psi_calculator, csi_calculator
└── templates/           # Copied on `prism init` — _quarto.yml, _common/*.qmd, example config+report
```

## Key Design Decisions

- Metrics register themselves via `@register_metric("metric_id")` decorator at import time
- All metric functions return dicts with a scalar `color_field` (for RAG evaluation) plus DataFrames/charts for display
- `Report` class caches everything after `compute_all()` — all subsequent calls are lookups, no re-computation
- YAML configs per model define: metric selection, thresholds, color rules, and aggregation strategy
- Templates use Quarto `{{< include >}}` for shared sections across models

## Development

```bash
pip3 install -e ".[dev]"
python3 -m pytest tests/ -v     # 71 tests
prism --help                    # CLI commands
prism init my-project           # Scaffold a new report project
```

## Dependencies

- Runtime: pyyaml, click, pandas, plotly, tabulate
- External: Quarto CLI must be on PATH for rendering
- Optional: `cap` package for CAP-sourced metrics
- Dev: pytest, pytest-cov
