"""
Declarative Tool Definitions for the AI BI Agent.
Exposes narrowly-scoped tools with strict schemas conforming to OpenAI/Anthropic/Gemini tool-calling standards.
"""

from __future__ import annotations

from typing import Any, Dict, List


def get_agent_tools() -> List[Dict[str, Any]]:
    """Return tool schemas in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_available_datasets",
                "description": "Lists all datasets available to the current organization with their table names and row counts.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "inspect_dataset_schema",
                "description": "Inspects the column names, data types, and sample preview data for a specific dataset.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "The UUID of the dataset to inspect.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "validate_query",
                "description": "Deterministically checks that a proposed SQL query is safe, read-only, references valid tables, and does not contain DDL/DML.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "The UUID of the dataset target.",
                        },
                        "sql_query": {
                            "type": "string",
                            "description": "The SQL SELECT statement to validate.",
                        },
                    },
                    "required": ["dataset_id", "sql_query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute_read_only_query",
                "description": "Executes an approved, read-only SQL query against the dataset and returns actual data rows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "The UUID of the dataset.",
                        },
                        "sql_query": {
                            "type": "string",
                            "description": "The verified read-only SQL query to run.",
                        },
                    },
                    "required": ["dataset_id", "sql_query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_statistics",
                "description": "Computes statistical summary (mean, median, standard deviation, min, max, percentiles) for a numeric column in the dataset.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "metric_column": {"type": "string"},
                    },
                    "required": ["dataset_id", "metric_column"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_chart_specification",
                "description": "Generates a validated chart configuration (line, bar, scatter, etc.) from real query result columns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chart_type": {
                            "type": "string",
                            "enum": ["line", "bar", "stacked_bar", "scatter", "table", "kpi_card"],
                            "description": "The type of visualization.",
                        },
                        "title": {"type": "string"},
                        "x_axis": {"type": "string"},
                        "y_axis": {"type": "string"},
                    },
                    "required": ["chart_type", "title", "x_axis", "y_axis"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_anomaly_detection",
                "description": "Runs statistical anomaly detection on a numeric or time-series column to detect unexpected deviations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "metric_column": {"type": "string"},
                        "time_column": {"type": "string"},
                        "method": {
                            "type": "string",
                            "enum": ["z_score", "iqr"],
                            "default": "z_score",
                        },
                    },
                    "required": ["dataset_id", "metric_column"],
                },
            },
        },
    ]
