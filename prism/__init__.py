"""PRISM — Performance Reporting & Insight for Standardized Monitoring.

Public API:
    Report          Main interface for .qmd report files
    MetricResolver  Routes metric calls to local or CAP backend
    evaluate_color  Apply RAG thresholds to a single value
    format_badge    Render a RAG color badge as HTML
    format_table    Render a DataFrame as markdown
"""

from prism.colors import evaluate_color
from prism.connector import SnowflakeConnector
from prism.core import Report
from prism.helpers import format_badge, format_commentary, format_table
from prism.resolver import MetricResolver

# Trigger metric registration on import
import prism.metrics  # noqa: F401

__all__ = [
    "Report",
    "MetricResolver",
    "SnowflakeConnector",
    "evaluate_color",
    "format_badge",
    "format_commentary",
    "format_table",
]
