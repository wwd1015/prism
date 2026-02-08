# PRISM — Performance Reporting & Insight for Standardized Monitoring

PRISM generates shareable model monitoring reports (HTML, PDF, slides) using Quarto as the rendering engine. It provides a RAG (Red/Amber/Green) color system with multi-layer aggregation for model health assessment.

## Installation

```bash
pip install -e ".[dev]"
```

**Requirement:** [Quarto CLI](https://quarto.org/docs/get-started/) must be installed separately.

## Quick Start

```bash
# Create a new report project
prism init my-reports
cd my-reports

# Add a model
prism add-model revenue_predictor

# Edit config/models/revenue_predictor.yaml with your metrics
# Render the report
prism render revenue_predictor
```

## Usage in .qmd Files

```python
from prism import Report

report = Report(model_id="model_a", config_dir="config")
report.compute_all(data=df)

# All metrics are now cached — use anywhere in the report:
report.header()                      # Model name + final RAG badge
report.scorecard()                   # Full metric scorecard table
report.metric("rank_ordering")       # Cached metric result dict
report.metric_color("rank_ordering") # "green", "yellow", or "red"
report.final_color()                 # Overall model color
```

## Configuration

Each model has a YAML config (`config/models/<model_id>.yaml`) specifying:
- **Metrics**: which metrics to compute, their thresholds, and RAG color rules
- **Aggregation**: how metric colors roll up to sector colors and a final model color

## CLI Commands

| Command | Description |
|---------|-------------|
| `prism init <name>` | Create a new report project |
| `prism add-model <id>` | Add a model config + report template |
| `prism render <id>` | Render one model's report |
| `prism render-all` | Render all configured models |
| `prism list` | List configured models |
| `prism validate` | Validate YAML configs |
| `prism preview <id>` | Render HTML and open in browser |

## Built-in Metrics

| Metric ID | Description |
|-----------|-------------|
| `gini_coefficient` | Gini coefficient for discriminatory power |
| `ks_statistic` | Kolmogorov-Smirnov statistic |
| `model_accuracy` | AUC, accuracy, precision, recall |
| `precision_recall` | Precision, recall, F1 at threshold |
| `psi_calculator` | Population Stability Index |
| `csi_calculator` | Characteristic Stability Index |

## CAP Integration

PRISM works standalone with built-in metrics. When CAP becomes available, switch `source: local` to `source: cap` in your YAML config — no report code changes needed.

## Development

```bash
pip install -e ".[dev]"
pytest
```
