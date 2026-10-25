"""
Chart Specification & Recommendation Service.
Inspects query results, selects the optimal visualization type, and produces deterministic, sanitized ChartSpec objects.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from app.schemas.chart import AxisConfig, ChartFilter, ChartSpec, ChartType, SeriesConfig


class ChartService:
    @staticmethod
    def recommend_chart(
        data: List[Dict[str, Any]],
        columns: List[str],
        title_hint: Optional[str] = None,
    ) -> ChartSpec:
        """
        Analyze columns and row patterns to recommend and generate a validated ChartSpec.
        """
        if not data or not columns:
            return ChartSpec(
                chart_type=ChartType.TABLE,
                title=title_hint or "Query Results",
                x_axis=AxisConfig(field=columns[0]) if columns else None,
                y_axis=AxisConfig(field="Value"),
                data=[],
            )

        # 1. Single row, single numeric column -> KPI Card
        if len(data) == 1 and len(columns) <= 2:
            num_col = None
            for col in columns:
                val = data[0].get(col)
                if isinstance(val, (int, float)):
                    num_col = col
                    break
            if num_col:
                val_num = data[0].get(num_col)
                formatted_val = f"{val_num:,.2f}" if isinstance(val_num, float) else f"{val_num:,}"
                return ChartSpec(
                    chart_type=ChartType.KPI_CARD,
                    title=title_hint or num_col.replace("_", " ").title(),
                    kpi_value=formatted_val,
                    data=data,
                )

        # 2. Check for date/time columns
        date_col = None
        for col in columns:
            col_lower = col.lower()
            if any(term in col_lower for term in ["date", "time", "month", "year", "day", "quarter", "week", "created"]):
                date_col = col
                break

        # Check for numeric columns
        numeric_cols = []
        for col in columns:
            if col == date_col:
                continue
            is_num = any(isinstance(r.get(col), (int, float)) for r in data[:5])
            if is_num:
                numeric_cols.append(col)

        # Categorical columns
        categorical_cols = [c for c in columns if c not in numeric_cols and c != date_col]

        # 3. If date column and numeric column exist -> LINE chart (Time series)
        if date_col and numeric_cols:
            return ChartSpec(
                chart_type=ChartType.LINE,
                title=title_hint or f"{numeric_cols[0].replace('_', ' ').title()} Over Time",
                x_axis=AxisConfig(field=date_col, label=date_col.replace("_", " ").title()),
                y_axis=AxisConfig(field=numeric_cols[0], label=numeric_cols[0].replace("_", " ").title()),
                series=[SeriesConfig(field=c, label=c.replace("_", " ").title()) for c in numeric_cols],
                data=data[:500],
            )

        # 4. If categorical + numeric -> BAR chart or STACKED_BAR
        if categorical_cols and numeric_cols:
            chart_type = ChartType.BAR if len(numeric_cols) == 1 else ChartType.STACKED_BAR
            return ChartSpec(
                chart_type=chart_type,
                title=title_hint or f"{numeric_cols[0].replace('_', ' ').title()} by {categorical_cols[0].replace('_', ' ').title()}",
                x_axis=AxisConfig(field=categorical_cols[0], label=categorical_cols[0].replace("_", " ").title()),
                y_axis=AxisConfig(field=numeric_cols[0], label=numeric_cols[0].replace("_", " ").title()),
                series=[SeriesConfig(field=c, label=c.replace("_", " ").title()) for c in numeric_cols],
                data=data[:50],
            )

        # 5. Two numeric columns without clear categories -> SCATTER plot
        if len(numeric_cols) >= 2 and not categorical_cols:
            return ChartSpec(
                chart_type=ChartType.SCATTER,
                title=title_hint or f"{numeric_cols[0]} vs {numeric_cols[1]}",
                x_axis=AxisConfig(field=numeric_cols[0], label=numeric_cols[0].replace("_", " ").title()),
                y_axis=AxisConfig(field=numeric_cols[1], label=numeric_cols[1].replace("_", " ").title()),
                series=[SeriesConfig(field=numeric_cols[1], label=numeric_cols[1].replace("_", " ").title())],
                data=data[:500],
            )

        # 6. Default to TABLE for multi-column or unstructured query results
        return ChartSpec(
            chart_type=ChartType.TABLE,
            title=title_hint or "Detailed Records",
            x_axis=AxisConfig(field=columns[0]),
            y_axis=AxisConfig(field=columns[1] if len(columns) > 1 else columns[0]),
            series=[SeriesConfig(field=c) for c in columns],
            data=data[:100],
        )
