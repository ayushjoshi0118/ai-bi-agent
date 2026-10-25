"""
Semantic Metric Catalog.
Defines explicit business metric models, formulas, dimensions, units, owners,
filter conditions, and null-handling semantics.
Guarantees reproducible, audit-traceable business calculations without hallucinated SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import numpy as np
import pandas as pd


class MetricUnit(str, Enum):
    CURRENCY_USD = "USD"
    CURRENCY_EUR = "EUR"
    PERCENTAGE = "%"
    COUNT = "count"
    RATIO = "ratio"
    TIME_SECONDS = "seconds"
    TIME_DAYS = "days"


class TimeGrain(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class MetricDefinition:
    id: str
    name: str
    description: str
    formula_sql: str
    unit: MetricUnit
    dimensions: List[str]
    owner: str
    applicable_filters: List[str] = field(default_factory=list)
    null_handling: str = "COALESCE(metric, 0)"
    default_time_grain: TimeGrain = TimeGrain.DAILY
    synonyms: List[str] = field(default_factory=list)
    is_additive: bool = True
    compute_fn: Optional[Callable[[pd.DataFrame], float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "formula_sql": self.formula_sql,
            "unit": self.unit.value,
            "dimensions": self.dimensions,
            "owner": self.owner,
            "applicable_filters": self.applicable_filters,
            "null_handling": self.null_handling,
            "default_time_grain": self.default_time_grain.value,
            "synonyms": self.synonyms,
            "is_additive": self.is_additive,
        }


class SemanticMetricCatalog:
    """
    Registry for organization and domain semantic business metrics.
    Ensures natural-language questions map to mathematically grounded,
    pre-approved business calculations rather than invented model guesses.
    """

    def __init__(self):
        self._metrics: Dict[str, MetricDefinition] = {}
        self._register_standard_metrics()

    def register_metric(self, metric: MetricDefinition) -> None:
        self._metrics[metric.id.lower()] = metric

    def get_metric(self, metric_id: str) -> Optional[MetricDefinition]:
        return self._metrics.get(metric_id.lower())

    def list_metrics(self) -> List[MetricDefinition]:
        return list(self._metrics.values())

    def search_by_term(self, term: str) -> List[MetricDefinition]:
        """Search metrics by ID, name, description, or synonyms."""
        q = term.lower().strip()
        matches = []
        for m in self._metrics.values():
            if (
                q in m.id
                or q in m.name.lower()
                or q in m.description.lower()
                or any(q in s.lower() for s in m.synonyms)
            ):
                matches.append(m)
        return matches

    def _register_standard_metrics(self) -> None:
        """Populate core business intelligence metrics with explicit definitions."""

        # 1. Total / Net Revenue
        self.register_metric(
            MetricDefinition(
                id="revenue",
                name="Total Net Revenue",
                description="Total monetary value of successful sales after subtracting refunds and discounts.",
                formula_sql="SUM(COALESCE(revenue, amount, 0))",
                unit=MetricUnit.CURRENCY_USD,
                dimensions=["date", "region", "product_category", "customer_segment", "channel"],
                owner="Finance & Sales Operations",
                applicable_filters=["status != 'cancelled'", "status != 'refunded'"],
                null_handling="COALESCE to 0",
                synonyms=["sales", "turnover", "gross receipts", "top line revenue", "total sales"],
                is_additive=True,
                compute_fn=lambda df: float(df["revenue"].sum()) if "revenue" in df else float(df["amount"].sum()),
            )
        )

        # 2. Gross Profit
        self.register_metric(
            MetricDefinition(
                id="profit",
                name="Gross Profit",
                description="Net revenue remaining after deducting Cost of Goods Sold (COGS).",
                formula_sql="SUM(COALESCE(revenue, amount, 0) - COALESCE(cost, cogs, 0))",
                unit=MetricUnit.CURRENCY_USD,
                dimensions=["date", "region", "product_category"],
                owner="Corporate Finance",
                applicable_filters=["status = 'completed'"],
                null_handling="Cost defaults to 0 when unspecified",
                synonyms=["gross profit", "earnings", "gross margin dollars", "profitability"],
                is_additive=True,
                compute_fn=lambda df: float((df["revenue"] - df["cost"]).sum()),
            )
        )

        # 3. Conversion Rate
        self.register_metric(
            MetricDefinition(
                id="conversion_rate",
                name="Conversion Rate",
                description="Percentage of visitors or sessions that successfully complete a target conversion event.",
                formula_sql="ROUND(COUNT(DISTINCT CASE WHEN converted = 1 OR converted = TRUE THEN user_id END) * 100.0 / NULLIF(COUNT(DISTINCT user_id), 0), 2)",
                unit=MetricUnit.PERCENTAGE,
                dimensions=["date", "channel", "device", "campaign"],
                owner="Growth & Marketing Analytics",
                applicable_filters=["is_bot = FALSE"],
                null_handling="NULLIF denominator to prevent division by zero; returns 0.0 if empty",
                synonyms=["cvr", "session conversion", "lead conversion rate"],
                is_additive=False,
                compute_fn=lambda df: (
                    float((df["converted"].sum() / df["user_id"].nunique()) * 100.0)
                    if df["user_id"].nunique() > 0
                    else 0.0
                ),
            )
        )

        # 4. Customer Churn Rate
        self.register_metric(
            MetricDefinition(
                id="customer_churn",
                name="Customer Churn Rate",
                description="Percentage of active customers at the start of a period who discontinued subscription or churned.",
                formula_sql="ROUND(COUNT(DISTINCT CASE WHEN churned = 1 OR churned = TRUE THEN customer_id END) * 100.0 / NULLIF(COUNT(DISTINCT customer_id), 0), 2)",
                unit=MetricUnit.PERCENTAGE,
                dimensions=["cohort_month", "subscription_tier", "region"],
                owner="Customer Success & Retention",
                applicable_filters=["subscription_status IN ('active', 'churned')"],
                null_handling="NULLIF denominator returns NULL or 0% when initial customer count is zero",
                synonyms=["churn", "user churn", "attrition rate", "customer attrition"],
                is_additive=False,
                compute_fn=lambda df: (
                    float((df["churned"].sum() / df["customer_id"].nunique()) * 100.0)
                    if df["customer_id"].nunique() > 0
                    else 0.0
                ),
            )
        )

        # 5. Customer Retention Rate
        self.register_metric(
            MetricDefinition(
                id="retention",
                name="Customer Retention Rate",
                description="Percentage of customers from a cohort who remain active at the end of the specified evaluation period.",
                formula_sql="ROUND(COUNT(DISTINCT CASE WHEN retained = 1 OR retained = TRUE THEN customer_id END) * 100.0 / NULLIF(COUNT(DISTINCT customer_id), 0), 2)",
                unit=MetricUnit.PERCENTAGE,
                dimensions=["cohort_month", "plan_type", "channel"],
                owner="Customer Success & Product Analytics",
                applicable_filters=[],
                null_handling="Safe division with NULLIF",
                synonyms=["retention rate", "customer retention", "cohort retention"],
                is_additive=False,
                compute_fn=lambda df: (
                    float((df["retained"].sum() / df["customer_id"].nunique()) * 100.0)
                    if df["customer_id"].nunique() > 0
                    else 0.0
                ),
            )
        )

        # 6. Average Order Value (AOV)
        self.register_metric(
            MetricDefinition(
                id="aov",
                name="Average Order Value",
                description="Average monetary value spent by a customer per transaction.",
                formula_sql="ROUND(SUM(COALESCE(revenue, amount, 0)) * 1.0 / NULLIF(COUNT(DISTINCT order_id), 0), 2)",
                unit=MetricUnit.CURRENCY_USD,
                dimensions=["date", "region", "product_category", "customer_segment"],
                owner="E-Commerce Analytics",
                applicable_filters=["status = 'completed'"],
                null_handling="NULLIF denominator to prevent division by zero",
                synonyms=["aov", "average basket size", "avg transaction size", "mean order value"],
                is_additive=False,
                compute_fn=lambda df: (
                    float(df["revenue"].sum() / df["order_id"].nunique())
                    if df["order_id"].nunique() > 0
                    else 0.0
                ),
            )
        )

        # 7. Gross Margin %
        self.register_metric(
            MetricDefinition(
                id="gross_margin",
                name="Gross Margin Percentage",
                description="Gross profit expressed as a percentage of total revenue.",
                formula_sql="ROUND(SUM(revenue - cost) * 100.0 / NULLIF(SUM(revenue), 0), 2)",
                unit=MetricUnit.PERCENTAGE,
                dimensions=["product_category", "region", "quarter"],
                owner="Corporate Finance",
                applicable_filters=["revenue > 0"],
                null_handling="NULLIF denominator prevents division by zero when revenue is 0",
                synonyms=["margin", "gross profit margin", "margin percentage"],
                is_additive=False,
            )
        )

        # 8. Transaction / Order Count
        self.register_metric(
            MetricDefinition(
                id="order_count",
                name="Total Order Volume",
                description="Total count of unique transactions or orders executed.",
                formula_sql="COUNT(DISTINCT order_id)",
                unit=MetricUnit.COUNT,
                dimensions=["date", "status", "payment_method"],
                owner="Operations",
                applicable_filters=[],
                null_handling="COUNT returns 0 on empty sets",
                synonyms=["transactions", "order volume", "number of orders", "total orders", "sales volume"],
                is_additive=True,
                compute_fn=lambda df: (
                    float(df["order_id"].nunique()) if "order_id" in df else float(len(df))
                ),
            )
        )


# Global catalog instance
default_metric_catalog = SemanticMetricCatalog()
