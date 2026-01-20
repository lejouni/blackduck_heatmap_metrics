"""
Black Duck Heatmap Metrics Analyzer

A tool for analyzing Black Duck scan metrics from CSV files in zip archives.
Generates interactive HTML dashboards with time series analysis and filtering.
"""

__version__ = "0.1.5"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .analyzer import read_csv_from_zip, analyze_data, generate_chart_data, generate_html_report

__all__ = [
    "read_csv_from_zip",
    "analyze_data",
    "generate_chart_data",
    "generate_html_report",
]
