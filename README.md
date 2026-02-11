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

report = Report(model_id="model_a", config_dir="config",
                commentary_file="path/to/commentary.xlsx",
                connector=None)  # optional SnowflakeConnector
report.compute_all(data=df)

# All metrics are now cached — use anywhere in the report:
report.header()                      # Model name + final RAG badge
report.scorecard()                   # Full metric scorecard table
report.metric("rank_ordering")       # Cached metric result dict
report.metric_color("rank_ordering") # "green", "yellow", or "red"
report.commentary("rank_ordering")   # MD commentary callout (or "")
report.final_color()                 # Overall model color
```

## RAG Color Pipeline

PRISM aggregates model health through three layers:

```
              Layer 1              Layer 2                Layer 3
          Metric Thresholds   Sector Aggregation     Final Aggregation
          ─────────────────   ──────────────────     ─────────────────

Gini 0.45 ──► green ─┐
                      ├──► disc_power: green ──┐
AUC  0.88 ──► green ─┘    (worst_color)       │
                                               ├──► matrix ──► FINAL: green
PSI  0.04 ──► green ─┐                        │
                      ├──► stability: green ──┘
CSI  0.06 ──► green ─┘    (weighted_average)
```

Sector aggregation methods: `worst_color`, `best_color`, `majority`, `weighted_average`, `matrix` — configurable per sector. See the [User Guide](docs/user-guide.md) for full details.

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

## MD Commentary

PRISM supports embedding Model Developer (MD) commentary alongside each metric in the final report. Commentary is maintained in a single Excel spreadsheet outside of PRISM — MDs fill it in, and PRISM picks it up at render time.

### Creating the Commentary File

Create an `.xlsx` file (e.g. `commentary.xlsx`) with **one tab per model**. The tab name must match the `model_id` exactly (e.g. a tab named `revenue_predictor` for model ID `revenue_predictor`).

Each tab should have the following columns:

| Column | Required | Description |
|--------|----------|-------------|
| `metric_key` | Yes | Must match the metric key in the model's YAML config (e.g. `rank_ordering`, `accuracy`, `psi`) |
| `commentary` | Yes | The MD's written interpretation or commentary for this metric |
| `author` | No | Name of the person who wrote the commentary |
| `date` | No | Date the commentary was written (any text format, e.g. `2025-01-15`) |

**Example spreadsheet layout** (tab: `revenue_predictor`):

| metric_key | commentary | author | date |
|---|---|---|---|
| rank_ordering | Gini coefficient declined from 0.52 to 0.45 due to portfolio composition shift in Q3. Will monitor for another quarter before recommending recalibration. | J. Smith | 2025-01-15 |
| accuracy | AUC remains within tolerance at 0.87. No action required. | J. Smith | 2025-01-15 |
| psi | PSI stable at 0.04. Population distribution unchanged. | A. Lee | 2025-01-20 |

Metrics without a row in the spreadsheet will simply have no commentary box in the report — this is fine and expected. You only need to add rows for metrics where commentary is relevant.

### Connecting the File to PRISM

Pass the path to your commentary file when creating a `Report`:

```python
report = Report(
    model_id="revenue_predictor",
    config_dir="config",
    commentary_file="path/to/commentary.xlsx",
)
```

Or, if using the default Quarto template, set `commentary_file` in your report parameters:

```yaml
params:
  model_id: "revenue_predictor"
  commentary_file: "path/to/commentary.xlsx"
```

### How It Renders

Commentary appears as a styled callout block after each metric's tables and charts:

> **MD Commentary**
>
> Gini coefficient declined from 0.52 to 0.45 due to portfolio composition shift in Q3. Will monitor for another quarter before recommending recalibration.
>
> *— J. Smith — 2025-01-15*

If no commentary file is provided, or if a metric has no entry, the report renders normally with no empty boxes or errors.

## Snowflake Connector

PRISM includes a reusable `SnowflakeConnector` for database access. It connects lazily on first query and defaults to environment variables (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, etc.):

```python
from prism import Report, SnowflakeConnector

with SnowflakeConnector() as conn:
    report = Report(model_id="model_a", connector=conn)
    report.compute_all(data=df)
```

Install the optional dependency: `pip install prism[snowflake]`

## CAP Integration

PRISM works standalone with built-in metrics. When CAP becomes available, switch `source: local` to `source: cap` in your YAML config — no report code changes needed. The `connector` parameter flows through automatically to CAP metric calls.

## Documentation

See the [User Guide](docs/user-guide.md) for complete documentation including:
- YAML configuration reference
- RAG color system (thresholds, sector aggregation, per-sector overrides, matrix rules)
- Built-in metrics and their parameters
- MD commentary setup
- Snowflake and CAP integration

## Development

```bash
pip install -e ".[dev]"
pytest
```
