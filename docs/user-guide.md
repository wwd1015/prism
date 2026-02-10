# PRISM User Guide

## 1. Introduction

PRISM (Performance Reporting & Insight for Standardized Monitoring) is a Python package that generates shareable model monitoring reports in HTML, PDF, and slide formats using [Quarto](https://quarto.org) as the rendering engine.

PRISM provides:

- **RAG color system** — Red/Amber/Green status indicators with multi-layer aggregation (metric → sector → final model color)
- **Built-in metrics** — Gini coefficient, KS statistic, AUC/accuracy/precision/recall, PSI, and CSI
- **Configurable via YAML** — Define metrics, thresholds, and aggregation rules per model
- **MD commentary** — Attach analyst commentary from an Excel spreadsheet
- **Reusable report sections** — Shared `.qmd` templates included across models
- **CLI** — Scaffold projects, render reports, validate configs from the command line

**Who is this for?** Model risk teams, data scientists, and validation analysts who need standardized, repeatable monitoring reports for production models.

## 2. Installation

### Install PRISM

```bash
pip install -e ".[dev]"
```

Or install from the package directly:

```bash
pip install prism
```

### Install Quarto CLI

PRISM uses Quarto to render reports. Install it from:

- **macOS**: `brew install quarto` or download from [quarto.org](https://quarto.org/docs/get-started/)
- **Linux**: Download the `.deb` or `.tar.gz` from [quarto.org](https://quarto.org/docs/get-started/)
- **Windows**: Download the `.msi` installer from [quarto.org](https://quarto.org/docs/get-started/)

Verify the installation:

```bash
quarto --version
```

### Python dependencies

PRISM requires Python 3.11+ and the following packages (installed automatically):

| Package | Purpose |
|---------|---------|
| `pyyaml` | YAML config parsing |
| `click` | CLI framework |
| `pandas` | DataFrames for metric results |
| `plotly` | Interactive charts |
| `tabulate` | Markdown table rendering |
| `numpy` | Numerical computation |
| `openpyxl` | Excel commentary file reading |

## 3. Quick Start

The fastest way to get started is with the included quickstart example.

### Option A: Use the quickstart example

```bash
cd examples/quickstart

# Generate sample data (already pre-committed, but you can regenerate)
python generate_data.py

# Render the report
quarto render reports/credit_risk_model/monitoring.qmd --to html

# Open the report
open _output/reports/credit_risk_model/monitoring.html
```

### Option B: Scaffold a new project

```bash
# Create a new project from built-in templates
prism init my-monitoring-project
cd my-monitoring-project

# The project comes with an example model — render it
prism render example_model

# Open in browser
prism preview example_model
```

### Option C: Add a model to an existing project

```bash
cd my-monitoring-project

# Add a new model config + report file
prism add-model credit_risk_v2

# Edit the generated config
# config/models/credit_risk_v2.yaml

# Render
prism render credit_risk_v2
```

## 4. Project Structure

A PRISM project has the following layout:

```
my-project/
├── _quarto.yml                    # Quarto project configuration
├── _common/                       # Shared report sections
│   ├── setup.qmd                  # Phase 1: data loading + compute_all()
│   ├── header.qmd                 # Model name + RAG badge
│   ├── scorecard.qmd              # Full scorecard table
│   ├── rank_ordering.qmd          # Gini coefficient section
│   ├── accuracy.qmd               # AUC/accuracy section
│   └── footer.qmd                 # Generated timestamp
├── config/
│   ├── project.yaml               # Project-level settings
│   ├── commentary.xlsx            # MD commentary spreadsheet (optional)
│   └── models/
│       ├── model_a.yaml           # Per-model configuration
│       └── model_b.yaml
├── reports/
│   ├── model_a/
│   │   └── monitoring.qmd         # Main report file for model_a
│   └── model_b/
│       └── monitoring.qmd
├── data/                          # Data files (CSV, parquet, etc.)
└── _output/                       # Rendered reports (HTML, PDF)
```

### Key files

| File | Purpose |
|------|---------|
| `_quarto.yml` | Quarto project config — sets output directory, format defaults |
| `config/project.yaml` | Project settings — output dir, format, commentary file path |
| `config/models/<model_id>.yaml` | Per-model config — metrics, thresholds, aggregation |
| `_common/setup.qmd` | Loads data, initializes `Report`, calls `compute_all()` |
| `reports/<model_id>/monitoring.qmd` | Main report — includes shared sections via `{{< include >}}` |

## 5. Model Configuration

Each model has a YAML configuration file at `config/models/<model_id>.yaml`. This file defines which metrics to compute, their thresholds, and how to aggregate colors.

### Full example

```yaml
model_id: credit_risk_model
model_name: "Credit Risk Model v2.1"
model_owner: "Model Risk Team"
tags: [credit, retail]

metrics:
  rank_ordering:
    sector: discriminatory_power
    metric_id: gini_coefficient
    source: local
    inputs:
      segment: "all"
    color_field: "gini_value"
    color:
      green: ">= 0.4"
      yellow: ">= 0.3"
      red: "< 0.3"

  accuracy:
    sector: discriminatory_power
    metric_id: model_accuracy
    source: local
    inputs:
      method: "auc"
    color_field: "auc_value"
    color:
      green: ">= 0.85"
      yellow: ">= 0.75"
      red: "< 0.75"

  psi:
    sector: stability
    metric_id: psi_calculator
    source: local
    inputs: {}
    color_field: "psi_value"
    color:
      green: "< 0.1"
      yellow: "< 0.25"
      red: ">= 0.25"

aggregation:
  sector:
    method: worst_color
  final:
    method: matrix
    dimensions: [discriminatory_power, stability]
    matrix:
      green:
        green: green
        yellow: yellow
        red: red
      yellow:
        green: yellow
        yellow: yellow
        red: red
      red:
        green: red
        yellow: red
        red: red
```

### Field reference

**Top-level fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `model_id` | Yes | Unique identifier, matches filename and report directory |
| `model_name` | No | Display name in reports (defaults to model_id) |
| `model_owner` | No | Team or owner name |
| `tags` | No | List of tags for filtering during batch renders |

**Metric fields** (under `metrics.<key>`):

| Field | Required | Description |
|-------|----------|-------------|
| `sector` | Yes | Grouping for sector-level aggregation (e.g. `discriminatory_power`, `stability`) |
| `metric_id` | Yes | Registered metric function name (e.g. `gini_coefficient`) |
| `source` | No | `local` (default) or `cap` for CAP backend |
| `inputs` | No | Dict of extra keyword arguments passed to the metric function |
| `color_field` | Yes | Which key in the metric result dict holds the scalar for RAG evaluation |
| `color` | Yes | Threshold expressions for each color |

**Threshold expressions:**

Thresholds use comparison operators with numeric values:

```yaml
color:
  green: ">= 0.4"    # Green if value >= 0.4
  yellow: ">= 0.3"   # Yellow if value >= 0.3 (and not green)
  red: "< 0.3"       # Red if value < 0.3
```

Supported operators: `>=`, `<=`, `>`, `<`, `==`, `!=`

Colors are evaluated in priority order: green → yellow → red. The first match wins.

**For "lower is better" metrics** (like PSI), reverse the direction:

```yaml
color:
  green: "< 0.1"     # Green if PSI < 0.1
  yellow: "< 0.25"   # Yellow if PSI < 0.25
  red: ">= 0.25"     # Red if PSI >= 0.25
```

## 6. RAG Color System

PRISM uses a three-layer color aggregation pipeline:

### Layer 1: Individual Metric Colors

Each metric's scalar value is evaluated against its `color` thresholds. For example, a Gini of 0.45 with thresholds `green: ">= 0.4"` → **Green**.

### Layer 2: Sector Aggregation

Metrics are grouped by `sector`. Within each sector, colors are combined using one of these methods:

| Method | Behavior |
|--------|----------|
| `worst_color` | The worst (most severe) color in the sector. If any metric is red, the sector is red. |
| `best_color` | The best color in the sector. If any metric is green, the sector is green. |
| `majority` | The color that appears most often. Tie-breaks favor the worst color. |

Configure in the aggregation section:

```yaml
aggregation:
  sector:
    method: worst_color   # or best_color, majority
```

### Layer 3: Final Model Color

Sector colors are combined into a single final model color. Two methods:

**Worst color** (default): The worst color across all sectors.

```yaml
aggregation:
  final:
    method: worst_color
```

**Matrix**: A 2D mapping matrix that defines how each pair of sector colors combines. For N sectors, the matrix is applied iteratively (pairwise from left to right).

```yaml
aggregation:
  final:
    method: matrix
    dimensions: [discriminatory_power, stability]
    matrix:
      green:
        green: green
        yellow: yellow
        red: red
      yellow:
        green: yellow
        yellow: yellow
        red: red
      red:
        green: red
        yellow: red
        red: red
```

Read the matrix as: `matrix[sector1_color][sector2_color] → final_color`. For example, if discriminatory_power is green and stability is yellow, the final color is yellow.

### Visual summary

```
Gini → green  ─┐
                ├─ discriminatory_power: green (worst_color) ─┐
AUC  → green  ─┘                                              │
                                                               ├─ matrix → green (final)
PSI  → green  ─── stability: green (worst_color) ────────────┘
```

## 7. Built-in Metrics

### Gini Coefficient (`gini_coefficient`)

Measures model discriminatory power using the Lorenz curve.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `actual_col` | `"actual"` | Binary outcome column (0/1) |
| `predicted_col` | `"predicted"` | Predicted score column |
| `segment` | `"all"` | Segment filter (or `"all"` for full data) |

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `gini_value` | float | Gini coefficient (0 = random, 1 = perfect) |
| `summary` | DataFrame | Decile-level summary (count, event_rate, avg_score) |
| `lorenz_chart` | Plotly Figure | Lorenz curve visualization |

**Typical thresholds:**

```yaml
color:
  green: ">= 0.4"
  yellow: ">= 0.3"
  red: "< 0.3"
```

### KS Statistic (`ks_statistic`)

Measures the maximum separation between cumulative event and non-event distributions.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `actual_col` | `"actual"` | Binary outcome column (0/1) |
| `predicted_col` | `"predicted"` | Predicted score column |

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `ks_value` | float | KS statistic (0 = no separation, 1 = perfect) |
| `ks_table` | DataFrame | Decile-level KS breakdown |

### Model Accuracy (`model_accuracy`)

Computes AUC, accuracy, precision, and recall.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `actual_col` | `"actual"` | Binary outcome column (0/1) |
| `predicted_col` | `"predicted"` | Predicted score column |
| `method` | `"auc"` | Primary metric: `"auc"`, `"accuracy"`, `"precision"`, or `"recall"` |
| `threshold` | `0.5` | Decision threshold for binary classification |

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `auc_value` | float | Area Under the ROC Curve |
| `accuracy_value` | float | (TP + TN) / Total |
| `precision_value` | float | TP / (TP + FP) |
| `recall_value` | float | TP / (TP + FN) |
| `confusion_matrix` | dict | `{tp, tn, fp, fn}` |
| `roc_chart` | Plotly Figure | ROC curve visualization |

**Typical thresholds (using AUC):**

```yaml
color:
  green: ">= 0.85"
  yellow: ">= 0.75"
  red: "< 0.75"
```

### PSI Calculator (`psi_calculator`)

Measures Population Stability Index — how much the score distribution has shifted from a reference.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `score_col` | `"predicted"` | Current score column |
| `reference_col` | `"reference_score"` | Reference score column (if present in data) |
| `reference_period` | `None` | If set, uses `period_col` to split reference vs. current |
| `period_col` | `"period"` | Column identifying time period |
| `n_bins` | `10` | Number of bins for PSI calculation |

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `psi_value` | float | Total PSI (0 = no shift) |
| `psi_table` | DataFrame | Per-bin PSI breakdown |
| `psi_chart` | Plotly Figure | Expected vs. actual distribution bar chart |

**Typical thresholds:**

```yaml
color:
  green: "< 0.1"
  yellow: "< 0.25"
  red: ">= 0.25"
```

**Interpretation:** PSI < 0.1 means insignificant shift, 0.1–0.25 means moderate shift, > 0.25 means significant shift.

### CSI Calculator (`csi_calculator`)

Computes Characteristic Stability Index across input features.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `feature_cols` | `None` | List of feature columns (auto-detected if `None`) |
| `reference_col_suffix` | `"_ref"` | Suffix for reference columns (e.g. `age` vs `age_ref`) |
| `n_bins` | `10` | Number of bins per feature |

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `csi_value` | float | Maximum PSI across all features |
| `csi_table` | DataFrame | Per-feature PSI summary |
| `feature_details` | dict | Per-feature bin-level PSI tables |

## 8. MD Commentary

PRISM supports attaching model developer (MD) commentary to metric sections via an Excel spreadsheet.

### Creating the commentary file

Create an Excel file (`.xlsx`) with **one tab per model**. The tab name must match the `model_id`.

Each tab needs these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `metric_key` | Yes | Matches the metric key in the YAML config (e.g. `rank_ordering`) |
| `commentary` | Yes | Free-text commentary |
| `author` | No | Author attribution |
| `date` | No | Date of commentary |

**Example:**

| metric_key | commentary | author | date |
|------------|-----------|--------|------|
| rank_ordering | Gini remains above 0.40, indicating good discriminatory power. | Model Risk Team | 2024-12-01 |
| accuracy | AUC is stable and well above the 0.85 green threshold. | Model Risk Team | 2024-12-01 |
| psi | PSI is within acceptable limits (below 0.10). | Model Risk Team | 2024-12-01 |

### Connecting commentary to the report

Set the commentary file path in `config/project.yaml`:

```yaml
commentary_file: config/commentary.xlsx
```

Or pass it directly when initializing the Report:

```python
report = Report(
    model_id="credit_risk_model",
    commentary_file="config/commentary.xlsx",
)
```

Commentary appears as styled callout boxes in the rendered report after each metric section.

## 9. Report Sections

### How templates work

Report sections are Quarto `.qmd` files in the `_common/` directory. The main report file (e.g. `reports/model_a/monitoring.qmd`) includes them using Quarto's include shortcode:

```markdown
{{< include ../../_common/setup.qmd >}}
{{< include ../../_common/header.qmd >}}
{{< include ../../_common/scorecard.qmd >}}
{{< include ../../_common/rank_ordering.qmd >}}
{{< include ../../_common/accuracy.qmd >}}
{{< include ../../_common/footer.qmd >}}
```

### Two-phase execution

PRISM uses a two-phase execution model:

1. **Phase 1 (setup.qmd)**: Loads data, creates the `Report` object, and calls `compute_all()`. This pre-computes every metric and every color before any rendering begins.

2. **Phase 2 (all other sections)**: Sections access cached results via `report.metric()`, `report.scorecard()`, etc. No re-computation occurs.

This architecture solves the "scorecard-at-top" problem — the scorecard needs all metric results, but it appears at the top of the report before any individual metric sections.

### Customizing sections

To add a new section, create a `.qmd` file in `_common/` and include it in your report:

```markdown
## My Custom Section

\```{python}
#| output: asis
#| echo: false
print(report.section_header("my_metric"))
\```

\```{python}
#| output: asis
#| echo: false
result = report.metric("my_metric")
print(report.table(result["summary"]))
\```

\```{python}
#| echo: false
fig = result.get("chart")
if fig:
    fig.show()
\```

\```{python}
#| output: asis
#| echo: false
print(report.commentary("my_metric"))
\```
```

### Available Report methods

| Method | Returns | Description |
|--------|---------|-------------|
| `report.header()` | str | Model name, date, and final color badge |
| `report.scorecard()` | str | Full scorecard table with sector subtotals |
| `report.section_header(key)` | str | Section heading with metric color badge |
| `report.metric(key)` | dict | Full cached metric result |
| `report.metric_value(key, field)` | any | Specific field from metric result |
| `report.metric_color(key)` | str | RAG color for a single metric |
| `report.sector_colors()` | dict | Sector → color mapping |
| `report.final_color()` | str | Final model color |
| `report.table(df)` | str | DataFrame as markdown table |
| `report.badge(color, label)` | str | Inline HTML color badge |
| `report.commentary(key)` | str | Formatted commentary callout (or empty string) |

## 10. CLI Reference

### `prism init <project-name>`

Create a new report project from built-in templates.

```bash
prism init my-project
```

Creates the full directory structure with example config and report files.

### `prism add-model <model_id>`

Add a new model configuration and report `.qmd` file.

```bash
prism add-model credit_risk_v2
```

Creates:
- `config/models/credit_risk_v2.yaml` — Model config with a default Gini metric
- `reports/credit_risk_v2/monitoring.qmd` — Report file with standard includes

### `prism render <model_id>`

Render a single model's report.

```bash
prism render credit_risk_model
prism render credit_risk_model --format html
prism render credit_risk_model --format pdf --date 2024-12-01
prism render credit_risk_model --output-dir custom_output/
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | All formats | `html`, `pdf`, or `revealjs` |
| `--output-dir` | `_output` | Output directory |
| `--date` | Today | Report date (YYYY-MM-DD) |

### `prism render-all`

Batch render all configured models.

```bash
prism render-all
prism render-all --tag credit --format html
```

| Option | Default | Description |
|--------|---------|-------------|
| `--tag` | None | Only render models with this tag |
| `--format` | All formats | Output format |
| `--output-dir` | `_output` | Output directory |
| `--date` | Today | Report date |

### `prism list`

List all configured models.

```bash
prism list
```

Output:

```
Model ID                  Name                                Tags
--------------------------------------------------------------------------------
credit_risk_model         Credit Risk Model v2.1              credit, retail
fraud_model               Fraud Detection Model               fraud
```

### `prism validate`

Validate all YAML model configurations.

```bash
prism validate
```

Checks for:
- Valid YAML syntax
- Required fields: `model_id`, `metrics`
- Each metric has `metric_id` and `color` thresholds

### `prism preview <model_id>`

Render HTML and open in browser.

```bash
prism preview credit_risk_model
prism preview credit_risk_model --date 2024-12-01
```

## 11. Writing Custom Metrics

### The `@register_metric` pattern

PRISM uses a decorator-based registry. To add a custom metric:

1. Create a Python file in `prism/metrics/` (or anywhere importable).
2. Decorate your function with `@register_metric("your_metric_id")`.
3. Import the module so registration happens at startup.

### Example: Custom concentration metric

```python
# prism/metrics/concentration.py

import pandas as pd
import numpy as np
from prism.metrics.registry import register_metric


@register_metric("herfindahl_index")
def herfindahl_index(
    data: pd.DataFrame,
    group_col: str = "segment",
    value_col: str = "exposure",
    **kwargs,
) -> dict:
    """Calculate Herfindahl-Hirschman Index for portfolio concentration."""
    totals = data.groupby(group_col)[value_col].sum()
    shares = totals / totals.sum()
    hhi = float((shares ** 2).sum())

    summary = pd.DataFrame({
        "segment": totals.index,
        "exposure": totals.values,
        "share": shares.values,
    })

    return {
        "hhi_value": round(hhi, 6),
        "summary": summary,
    }
```

### Registration requirements

Your metric function must:

1. Accept `data: pd.DataFrame` as the first argument (plus `**kwargs`)
2. Return a `dict` containing:
   - A scalar field for RAG evaluation (named to match `color_field` in the YAML config)
   - Optional: DataFrames, Plotly figures, or other display data

### Ensuring import

Add an import in `prism/metrics/__init__.py`:

```python
from prism.metrics import rank_ordering, accuracy, stability, concentration  # noqa: F401
```

### Using the custom metric in config

```yaml
metrics:
  concentration:
    sector: portfolio_quality
    metric_id: herfindahl_index
    source: local
    inputs:
      group_col: "segment"
      value_col: "exposure"
    color_field: "hhi_value"
    color:
      green: "< 0.15"
      yellow: "< 0.25"
      red: ">= 0.25"
```

## 12. Troubleshooting

### "Quarto CLI not found on PATH"

Install Quarto from [quarto.org/docs/get-started](https://quarto.org/docs/get-started/) and ensure it's on your PATH:

```bash
quarto --version   # Should print a version number
```

### "Model config not found"

Ensure the YAML file exists at `config/models/<model_id>.yaml` and the `model_id` matches the filename.

### "No module named 'nbclient'"

Quarto requires Jupyter dependencies for Python rendering:

```bash
pip install nbclient jupyter-client ipykernel
```

### "No threshold matched for value"

Your color thresholds don't cover all possible values. Ensure the green/yellow/red thresholds are exhaustive:

```yaml
# Good: covers all values
color:
  green: ">= 0.4"
  yellow: ">= 0.3"
  red: "< 0.3"

# Bad: gap between 0.3 and 0.4
color:
  green: "> 0.4"
  yellow: "< 0.3"
  red: "< 0.2"
```

### Charts not showing in rendered HTML

Ensure Plotly figures are displayed with `.show()`:

```python
fig = result.get("lorenz_chart")
if fig:
    fig.show()
```

In Quarto Python cells, Plotly figures inside `if` blocks need explicit `.show()` calls.

### "Report.compute_all() has not been called yet"

The `setup.qmd` must be included first in your report and must call `report.compute_all(data=data)`. Check that:

1. `{{< include ../../_common/setup.qmd >}}` is the first include
2. The `data` variable is properly loaded before `compute_all()`

### Commentary not appearing

Check that:

1. The Excel file exists at the path specified
2. The tab name matches the `model_id` exactly
3. The tab has `metric_key` and `commentary` columns
4. The `metric_key` values match the keys in your YAML config

### PSI returns 0.0

The PSI calculator needs either:
- A `reference_score` column in the data, or
- A `reference_period` set in the metric inputs plus a `period` column

Check your data has the expected columns.
