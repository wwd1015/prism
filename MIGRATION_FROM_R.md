# Migrating from R to PRISM (Python)

This guide helps you migrate an existing R-based model monitoring workflow into the PRISM framework. It covers concept mapping, metric migration, report template conversion, and recipes for common R patterns.

---

## Table of Contents

1. [Conceptual Mapping](#1-conceptual-mapping)
2. [Project Structure: Before and After](#2-project-structure-before-and-after)
3. [Migrating Metric Functions](#3-migrating-metric-functions)
4. [Migrating Report Templates (.Rmd → .qmd)](#4-migrating-report-templates-rmd--qmd)
5. [Migrating Color / RAG Logic](#5-migrating-color--rag-logic)
6. [Migrating Config and Thresholds](#6-migrating-config-and-thresholds)
7. [Common R → Python Recipes](#7-common-r--python-recipes)
8. [Registering Custom Metrics](#8-registering-custom-metrics)
9. [Rendering and CLI](#9-rendering-and-cli)
10. [FAQ and Gotchas](#10-faq-and-gotchas)

---

## 1. Conceptual Mapping

| R Workflow | PRISM Equivalent | Notes |
|---|---|---|
| `.Rmd` report files | `.qmd` report files | Quarto is the successor to R Markdown; `.qmd` supports both R and Python chunks |
| `rmarkdown::render()` | `prism render <model_id>` | CLI-driven or `runner.render_report()` in Python |
| R functions for Gini, KS, PSI, etc. | `prism/metrics/*.py` | Register via `@register_metric` decorator |
| Threshold checks (if/else in R) | `config/models/*.yaml` → `color:` section | Declarative YAML, no code needed |
| RAG aggregation logic in R | `prism/colors.py` | Built-in: `worst_color`, `best_color`, `majority`, `matrix` |
| `knitr` chunk options | Quarto cell options (`#\| echo: false`) | Similar but YAML-style syntax |
| `params` in YAML front matter | Same — `params:` in `.qmd` front matter | Quarto supports parameterized reports natively |
| `kableExtra` / `gt` / `DT` tables | `report.table(df)` → markdown table via `tabulate` | Or use Plotly `go.Table` for interactive tables |
| `ggplot2` charts | `plotly` charts | Quarto renders Plotly natively; see conversion recipes below |
| `source("utils.R")` | `from prism import Report` | All logic lives in the package, not sourced scripts |
| `lapply()` over models | `prism render-all` | Batch rendering with optional tag filtering |

---

## 2. Project Structure: Before and After

### Typical R structure

```
my-r-reports/
├── R/
│   ├── metrics.R            # Gini, KS, PSI functions
│   ├── colors.R             # RAG logic, thresholds
│   ├── utils.R              # Table formatting, helpers
│   └── render_all.R         # Loop over models, call rmarkdown::render()
├── templates/
│   ├── header.Rmd           # child doc for header
│   ├── scorecard.Rmd        # child doc for scorecard
│   └── rank_ordering.Rmd    # child doc for metric section
├── reports/
│   ├── model_a.Rmd
│   └── model_b.Rmd
├── config/
│   └── thresholds.xlsx      # or .csv / hardcoded in R
└── output/
```

### PRISM structure (after `prism init`)

```
my-reports/
├── _common/
│   ├── setup.qmd            # replaces source("utils.R") + source("metrics.R")
│   ├── header.qmd           # replaces header.Rmd child doc
│   ├── scorecard.qmd        # replaces scorecard.Rmd child doc
│   ├── rank_ordering.qmd    # replaces rank_ordering.Rmd child doc
│   ├── accuracy.qmd
│   └── footer.qmd
├── config/
│   ├── project.yaml
│   └── models/
│       ├── model_a.yaml     # replaces thresholds.xlsx rows for model_a
│       └── model_b.yaml
├── reports/
│   ├── model_a/
│   │   └── monitoring.qmd   # replaces model_a.Rmd
│   └── model_b/
│       └── monitoring.qmd
├── _quarto.yml
└── _output/
```

**Key differences:**
- Thresholds and metric config move from R code / Excel into per-model YAML files
- Shared sections use Quarto `{{< include >}}` instead of R Markdown `child` documents
- All metric logic lives in the `prism` package, not in local `.R` files
- Custom metrics are registered in Python, not defined inline

---

## 3. Migrating Metric Functions

### R: Gini coefficient

```r
gini_coefficient <- function(data, actual_col = "actual", predicted_col = "predicted") {
  data <- data[order(-data[[predicted_col]]), ]
  n <- nrow(data)
  cum_actuals <- cumsum(data[[actual_col]]) / sum(data[[actual_col]])
  lorenz_x <- seq(0, 1, length.out = n + 1)
  lorenz_y <- c(0, cum_actuals)
  auc <- sum(diff(lorenz_x) * (lorenz_y[-1] + lorenz_y[-(n+1)]) / 2)
  gini <- 2 * auc - 1
  return(list(gini_value = gini, lorenz_x = lorenz_x, lorenz_y = lorenz_y))
}
```

### PRISM: Already built-in

The Gini coefficient is already registered as `gini_coefficient` in `prism/metrics/rank_ordering.py`. You just reference it in your YAML config:

```yaml
metrics:
  rank_ordering:
    metric_id: gini_coefficient   # built-in
    source: local
    color_field: "gini_value"
    color:
      green: ">= 0.4"
      yellow: ">= 0.3"
      red: "< 0.3"
```

### R: Custom metric → PRISM custom metric

If you have a custom R metric that isn't built-in, see [Section 8](#8-registering-custom-metrics) for how to register it.

---

## 4. Migrating Report Templates (.Rmd → .qmd)

### Step-by-step conversion

#### 1. Rename `.Rmd` → `.qmd`

Quarto `.qmd` files are nearly identical to `.Rmd`. Start by renaming.

#### 2. Convert chunk syntax

R Markdown chunks:
````markdown
```{r setup, include=FALSE}
library(tidyverse)
source("R/metrics.R")
```
````

Quarto Python chunks:
````markdown
```{python}
#| label: setup
#| include: false
from prism import Report
report = Report(model_id=params["model_id"])
report.compute_all(data=df)
```
````

#### 3. Convert child documents → includes

R Markdown child:
```markdown
```{r, child="templates/header.Rmd"}
```
```

Quarto include:
```markdown
{{< include ../../_common/header.qmd >}}
```

#### 4. Convert chunk options

| R Markdown | Quarto |
|---|---|
| `echo=FALSE` | `#\| echo: false` |
| `include=FALSE` | `#\| include: false` |
| `results='asis'` | `#\| output: asis` |
| `fig.width=10, fig.height=6` | `#\| fig-width: 10` and `#\| fig-height: 6` |
| `message=FALSE, warning=FALSE` | Set globally in `_quarto.yml` under `execute:` |

#### 5. Convert inline R → inline Python

R Markdown inline:
```markdown
The Gini coefficient is `r round(gini_result$gini_value, 4)`.
```

Quarto (use a Python chunk with `output: asis`):
````markdown
```{python}
#| output: asis
#| echo: false
print(f"The Gini coefficient is {report.metric_value('rank_ordering'):.4f}.")
```
````

### Full example: converting a metric section

**Before (R Markdown):**
````markdown
## Rank Ordering

```{r}
result <- gini_coefficient(data)
rag_color <- get_rag_color(result$gini_value, thresholds$gini)
```

```{r, results='asis'}
cat(paste0("### Gini: ", rag_badge(rag_color), "\n"))
```

```{r}
kable(result$summary_table) %>% kable_styling()
```

```{r, fig.width=10}
plot_lorenz(result)
```
````

**After (PRISM .qmd):**
````markdown
## Rank Ordering

```{python}
#| output: asis
#| echo: false
report.section_header("rank_ordering")
```

```{python}
#| echo: false
result = report.metric("rank_ordering")
report.table(result["summary"])
```

```{python}
#| echo: false
result["lorenz_chart"]
```
````

**What changed:**
- No manual metric computation — `report.metric()` returns cached results
- No manual RAG color logic — `section_header()` includes the badge automatically
- No `kable` / `kableExtra` — `report.table()` handles formatting
- Plotly figure replaces ggplot — Quarto renders it natively

---

## 5. Migrating Color / RAG Logic

### R: Typical RAG logic

```r
get_rag_color <- function(value, thresholds) {
  if (value >= thresholds$green) return("green")
  if (value >= thresholds$yellow) return("yellow")
  return("red")
}

# Sector aggregation
aggregate_sector <- function(colors) {
  if ("red" %in% colors) return("red")
  if ("yellow" %in% colors) return("yellow")
  return("green")
}
```

### PRISM: Declarative in YAML

All of this moves into the model's YAML config:

```yaml
metrics:
  rank_ordering:
    color_field: "gini_value"
    color:
      green: ">= 0.4"        # equivalent to: if (value >= 0.4) "green"
      yellow: ">= 0.3"       # equivalent to: if (value >= 0.3) "yellow"
      red: "< 0.3"           # equivalent to: else "red"

aggregation:
  sector:
    method: worst_color       # equivalent to: if ("red" %in% colors) "red" ...
  final:
    method: matrix
    dimensions: [discriminatory_power, stability]
    matrix:                   # 2D lookup table for final color
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

**No R or Python code needed for color logic.** PRISM handles it automatically during `compute_all()`.

If your R code has a custom aggregation matrix, simply transcribe it into the YAML `matrix:` section.

---

## 6. Migrating Config and Thresholds

### From Excel/CSV thresholds

If your R package reads thresholds from a spreadsheet:

```r
thresholds <- read_excel("config/thresholds.xlsx")
# thresholds has columns: model_id, metric, green, yellow, red
```

Convert each row into the corresponding model YAML:

| Excel Row | YAML Equivalent |
|---|---|
| `model_a, gini, 0.4, 0.3, 0.3` | `color: {green: ">= 0.4", yellow: ">= 0.3", red: "< 0.3"}` |
| `model_a, psi, 0.1, 0.25, 0.25` | `color: {green: "< 0.1", yellow: "< 0.25", red: ">= 0.25"}` |

**Tip:** Write a quick conversion script if you have many models:

```python
import pandas as pd
import yaml

df = pd.read_excel("thresholds.xlsx")
for model_id, group in df.groupby("model_id"):
    config = {"model_id": model_id, "metrics": {}}
    for _, row in group.iterrows():
        # Adapt the threshold direction based on your metric
        config["metrics"][row["metric"]] = {
            "metric_id": row["metric"],
            "source": "local",
            "color_field": f"{row['metric']}_value",
            "color": {
                "green": f">= {row['green']}",
                "yellow": f">= {row['yellow']}",
                "red": f"< {row['red']}",
            },
        }
    with open(f"config/models/{model_id}.yaml", "w") as f:
        yaml.dump(config, f, sort_keys=False)
```

### From hardcoded R thresholds

If thresholds are hardcoded in R:

```r
thresholds <- list(
  gini = list(green = 0.4, yellow = 0.3),
  psi  = list(green = 0.1, yellow = 0.25)
)
```

Transcribe directly into the YAML `color:` section of each metric (see Section 5).

---

## 7. Common R → Python Recipes

### Data manipulation

| R (dplyr) | Python (pandas) |
|---|---|
| `df %>% filter(x > 0)` | `df[df["x"] > 0]` or `df.query("x > 0")` |
| `df %>% mutate(y = x * 2)` | `df["y"] = df["x"] * 2` or `df.assign(y=df["x"] * 2)` |
| `df %>% group_by(g) %>% summarise(m = mean(x))` | `df.groupby("g")["x"].mean().reset_index(name="m")` |
| `df %>% arrange(desc(x))` | `df.sort_values("x", ascending=False)` |
| `df %>% select(a, b)` | `df[["a", "b"]]` |
| `df %>% left_join(df2, by = "id")` | `df.merge(df2, on="id", how="left")` |
| `n()` | `"count"` in `.agg()` |
| `quantile(x, 0.95)` | `np.quantile(x, 0.95)` or `df["x"].quantile(0.95)` |

### Metrics

| R | Python (PRISM built-in) |
|---|---|
| `pROC::auc(roc(actual, predicted))` | `metric_id: model_accuracy` with `method: auc` |
| `MLmetrics::Gini(predicted, actual)` | `metric_id: gini_coefficient` |
| `scorecard::perf_psi(...)` | `metric_id: psi_calculator` |
| `custom KS function` | `metric_id: ks_statistic` |
| `InformationValue::IV(...)` | Register as custom metric (see Section 8) |

### Charts: ggplot2 → Plotly

| ggplot2 | Plotly (Python) |
|---|---|
| `ggplot(df, aes(x, y)) + geom_line()` | `go.Figure(go.Scatter(x=df["x"], y=df["y"], mode="lines"))` |
| `ggplot(df, aes(x, y)) + geom_bar(stat="identity")` | `go.Figure(go.Bar(x=df["x"], y=df["y"]))` |
| `ggplot(df, aes(x, fill=group)) + geom_histogram()` | `px.histogram(df, x="x", color="group")` |
| `labs(title="...", x="...", y="...")` | `fig.update_layout(title="...", xaxis_title="...", yaxis_title="...")` |
| `theme_minimal()` | `fig.update_layout(template="plotly_white")` |
| `scale_color_manual(values=c(...))` | `fig.update_traces(marker_color=...)` |
| `facet_wrap(~group)` | `px.line(df, x="x", y="y", facet_col="group")` |

**Quick Plotly imports:**
```python
import plotly.graph_objects as go  # low-level (like ggplot2 geom_*)
import plotly.express as px        # high-level (like qplot)
```

### Tables

| R | PRISM |
|---|---|
| `knitr::kable(df)` | `report.table(df)` |
| `kableExtra::kable_styling(...)` | Styling handled by Quarto HTML theme |
| `DT::datatable(df)` | Use `go.Table` for interactive tables in HTML output |
| `gt::gt(df)` | `report.table(df)` (markdown) or use `great_tables` Python package |

---

## 8. Registering Custom Metrics

If you have R metrics that aren't built into PRISM, register them as custom Python metrics.

### R original

```r
information_value <- function(data, actual_col, predicted_col, n_bins = 10) {
  data$bin <- cut(data[[predicted_col]], breaks = n_bins)
  stats <- data %>%
    group_by(bin) %>%
    summarise(events = sum(.data[[actual_col]]), total = n())
  stats$non_events <- stats$total - stats$events
  stats$event_rate <- stats$events / sum(stats$events)
  stats$non_event_rate <- stats$non_events / sum(stats$non_events)
  stats$woe <- log(stats$event_rate / stats$non_event_rate)
  stats$iv_contrib <- (stats$event_rate - stats$non_event_rate) * stats$woe
  iv <- sum(stats$iv_contrib, na.rm = TRUE)
  return(list(iv_value = iv, iv_table = stats))
}
```

### Python equivalent — register with PRISM

Create a file (e.g., `my_metrics.py` in your project, or add to `prism/metrics/`):

```python
import numpy as np
import pandas as pd
from prism.metrics.registry import register_metric


@register_metric("information_value")
def information_value(
    data: pd.DataFrame,
    actual_col: str = "actual",
    predicted_col: str = "predicted",
    n_bins: int = 10,
    **kwargs,
) -> dict:
    """Calculate Information Value (IV)."""
    df = data.copy()
    df["bin"] = pd.qcut(df[predicted_col], q=n_bins, duplicates="drop")

    stats = df.groupby("bin", observed=True).agg(
        events=(actual_col, "sum"),
        total=(actual_col, "count"),
    ).reset_index()

    stats["non_events"] = stats["total"] - stats["events"]
    total_events = max(stats["events"].sum(), 1)
    total_non_events = max(stats["non_events"].sum(), 1)
    stats["event_rate"] = stats["events"] / total_events
    stats["non_event_rate"] = stats["non_events"] / total_non_events

    # Avoid log(0)
    stats["event_rate"] = stats["event_rate"].clip(lower=1e-8)
    stats["non_event_rate"] = stats["non_event_rate"].clip(lower=1e-8)

    stats["woe"] = np.log(stats["event_rate"] / stats["non_event_rate"])
    stats["iv_contrib"] = (stats["event_rate"] - stats["non_event_rate"]) * stats["woe"]
    iv_value = float(stats["iv_contrib"].sum())

    return {
        "iv_value": round(iv_value, 6),
        "iv_table": stats,
    }
```

Then reference it in your model YAML:

```yaml
metrics:
  info_value:
    sector: discriminatory_power
    metric_id: information_value
    source: local
    inputs:
      n_bins: 10
    color_field: "iv_value"
    color:
      green: ">= 0.3"
      yellow: ">= 0.1"
      red: "< 0.1"
```

**Important:** Make sure your custom metric file is imported before `report.compute_all()` is called. Add the import to `_common/setup.qmd`:

```qmd
```{python}
#| include: false
import my_metrics  # triggers @register_metric
from prism import Report
report = Report(model_id=params["model_id"])
report.compute_all(data=df)
```
```

---

## 9. Rendering and CLI

### R workflow

```r
# Render one model
rmarkdown::render("reports/model_a.Rmd", params = list(model_id = "model_a"))

# Render all models
models <- c("model_a", "model_b", "model_c")
for (m in models) {
  rmarkdown::render("reports/template.Rmd",
                    params = list(model_id = m),
                    output_file = paste0(m, "_report.html"))
}
```

### PRISM equivalent

```bash
# Render one model
prism render model_a
prism render model_a --format pdf

# Render all models
prism render-all

# Render only models tagged "weekly"
prism render-all --tag weekly

# Quick preview in browser
prism preview model_a

# Validate all configs before rendering
prism validate
```

---

## 10. FAQ and Gotchas

### Q: Can I keep some R chunks in my .qmd files?

Yes. Quarto supports both `{r}` and `{python}` chunks in the same document. You could keep some R code during migration:

````markdown
```{r}
library(ggplot2)
ggplot(mtcars, aes(mpg, hp)) + geom_point()
```
````

However, the `report` object and PRISM helpers are Python-only. For a full migration, convert all chunks to Python.

### Q: How do I pass data to the report?

In R you might do `rmarkdown::render(..., params = list(data_path = "data.csv"))`.

In PRISM, load data in `_common/setup.qmd`:

```python
import pandas as pd
data = pd.read_csv("path/to/data.csv")  # or from a database
report = Report(model_id=params["model_id"])
report.compute_all(data=data)
```

### Q: My R code uses `source()` for shared utility functions. What's the equivalent?

Put shared Python functions in a local module and import them. PRISM's `Report` class replaces most utility functions (tables, badges, colors). For anything else, create a `utils.py` alongside your reports and `import utils` in setup.qmd.

### Q: My thresholds differ by time period / segment. How do I handle that?

Create separate YAML configs per variant (e.g., `model_a_retail.yaml`, `model_a_wholesale.yaml`), or pass segment info via `inputs:` in the metric config and handle it inside the metric function.

### Q: I use `flexdashboard` / `shiny` for interactive reports. Does PRISM support that?

PRISM targets static report output (HTML, PDF, slides). For interactive dashboards, consider pairing PRISM with Quarto's [dashboard layout](https://quarto.org/docs/dashboards/) or keeping a separate Dash/Streamlit app. The same metric functions and `Report` class can be reused.

### Q: What about renv / packrat for reproducibility?

Use a Python virtual environment or `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install prism
```

Or use `pyproject.toml` with `pip install -e .` for the project itself.

### Q: My R package is version-controlled. How do I handle the transition?

Recommended approach:
1. Create a new branch for the Python migration
2. Run `prism init` to scaffold the project
3. Migrate one model at a time — convert its `.Rmd` → `.qmd` and YAML config
4. Validate: `prism render <model_id>` and compare output against the R version
5. Once all models are migrated, retire the R code

---

## Migration Checklist

- [ ] Install PRISM: `pip install -e ".[dev]"`
- [ ] Install Quarto: https://quarto.org/docs/get-started/
- [ ] Scaffold project: `prism init my-reports`
- [ ] Convert thresholds (Excel/CSV/hardcoded) → per-model YAML configs
- [ ] Identify which R metrics map to PRISM built-ins (Gini, KS, AUC, PSI, CSI)
- [ ] Register any custom R metrics as Python functions with `@register_metric`
- [ ] Convert `.Rmd` → `.qmd` for each model report
- [ ] Convert child documents → `{{< include >}}` shared sections
- [ ] Convert ggplot2 charts → Plotly
- [ ] Convert kable/gt tables → `report.table()`
- [ ] Replace inline R with Python chunks (`#| output: asis`)
- [ ] Test: `prism validate` then `prism render <model_id>` for each model
- [ ] Compare output against R versions for correctness
- [ ] Set up `prism render-all` for batch rendering
