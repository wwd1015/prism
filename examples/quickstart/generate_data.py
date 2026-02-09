#!/usr/bin/env python3
"""Generate sample data for the PRISM quickstart example.

Creates:
  - data/sample_scores.csv   — 500 rows of synthetic model scores
  - config/commentary.xlsx   — MD commentary spreadsheet
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ROWS = 500
OUTPUT_DIR = Path(__file__).parent


def generate_scores(rng: np.random.Generator) -> pd.DataFrame:
    """Generate synthetic binary classification scores.

    Produces a dataset with realistic separation between events (actual=1)
    and non-events (actual=0), plus a reference score column for PSI
    calculation and a period column.
    """
    # 20% event rate
    actual = rng.binomial(1, 0.20, size=N_ROWS)

    # Predicted scores: events get higher scores on average
    predicted = np.where(
        actual == 1,
        rng.beta(5, 2, size=N_ROWS),     # events: skewed high
        rng.beta(2, 5, size=N_ROWS),     # non-events: skewed low
    )
    predicted = np.clip(predicted, 0.01, 0.99)

    # Reference scores: similar distribution but from a "baseline" period
    # Slight shift to create non-zero PSI
    ref_actual = rng.binomial(1, 0.20, size=N_ROWS)
    reference_score = np.where(
        ref_actual == 1,
        rng.beta(5, 2, size=N_ROWS),
        rng.beta(2, 5, size=N_ROWS),
    )
    reference_score = np.clip(reference_score, 0.01, 0.99)

    # Assign periods: 4 quarters
    periods = rng.choice(
        ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"],
        size=N_ROWS,
        p=[0.25, 0.25, 0.25, 0.25],
    )

    return pd.DataFrame({
        "actual": actual,
        "predicted": np.round(predicted, 6),
        "reference_score": np.round(reference_score, 6),
        "period": periods,
    })


def generate_commentary() -> dict[str, pd.DataFrame]:
    """Create MD commentary as a dict of DataFrames (one per model tab)."""
    rows = [
        {
            "metric_key": "rank_ordering",
            "commentary": (
                "The Gini coefficient remains strong at above 0.40, indicating "
                "good discriminatory power. The model continues to separate "
                "events from non-events effectively across all deciles."
            ),
            "author": "Model Risk Team",
            "date": "2024-12-01",
        },
        {
            "metric_key": "accuracy",
            "commentary": (
                "AUC is stable and well above the 0.85 green threshold. "
                "Precision and recall are balanced, with no significant "
                "degradation since the last review period."
            ),
            "author": "Model Risk Team",
            "date": "2024-12-01",
        },
        {
            "metric_key": "psi",
            "commentary": (
                "Population Stability Index is within acceptable limits "
                "(below 0.10). The score distribution has not shifted "
                "materially from the reference population."
            ),
            "author": "Model Risk Team",
            "date": "2024-12-01",
        },
    ]
    return {"credit_risk_model": pd.DataFrame(rows)}


def main():
    rng = np.random.default_rng(SEED)

    # Generate and save scores
    scores_path = OUTPUT_DIR / "data" / "sample_scores.csv"
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_scores(rng)
    df.to_csv(scores_path, index=False)
    print(f"Created {scores_path}  ({len(df)} rows)")

    # Generate and save commentary
    commentary_path = OUTPUT_DIR / "config" / "commentary.xlsx"
    commentary_path.parent.mkdir(parents=True, exist_ok=True)
    sheets = generate_commentary()
    with pd.ExcelWriter(commentary_path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
    print(f"Created {commentary_path}  ({len(sheets)} tab(s))")


if __name__ == "__main__":
    main()
