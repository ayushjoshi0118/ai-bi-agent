"""
Ambiguity Detection and Clarification Engine.
Analyzes user questions against available schemas and the semantic metric catalog.
Detects ambiguous metric terms, missing time boundaries, ambiguous superlatives,
and missing metadata, asking explicit clarifying questions instead of silently guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set

from app.analytics.metrics import MetricDefinition, SemanticMetricCatalog, default_metric_catalog


class AmbiguityType(str, Enum):
    NONE = "none"
    AMBIGUOUS_METRIC = "ambiguous_metric"
    MISSING_TIME_HORIZON = "missing_time_horizon"
    AMBIGUOUS_SUPERLATIVE = "ambiguous_superlative"
    MULTIPLE_MATCHING_DATASETS = "multiple_matching_datasets"
    MISSING_SCHEMA_METADATA = "missing_schema_metadata"


@dataclass
class AmbiguityOption:
    label: str
    interpretation: str
    suggested_metric_id: Optional[str] = None
    suggested_sql_clause: Optional[str] = None


@dataclass
class AmbiguityResult:
    is_ambiguous: bool
    ambiguity_type: AmbiguityType
    clarifying_question: Optional[str] = None
    options: List[AmbiguityOption] = field(default_factory=list)
    candidate_metrics: List[MetricDefinition] = field(default_factory=list)
    explanation: Optional[str] = None


class AmbiguityDetector:
    """
    Detects semantic ambiguity in natural language business intelligence queries.
    Prevents silent errors, fabricated definitions, and hallucinated joins.
    """

    def __init__(self, catalog: Optional[SemanticMetricCatalog] = None):
        self.catalog = catalog or default_metric_catalog

    def analyze(
        self,
        question: str,
        available_datasets: List[Dict[str, Any]],
        context_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> AmbiguityResult:
        q_lower = question.lower().strip()

        # 1. Check for Ambiguous Superlatives ("top customer", "best product", "worst region")
        superlative_match = re.search(r"\b(top|best|worst|leading|most valuable)\s+(customer|user|client|product|item|region)\b", q_lower)
        if superlative_match:
            entity = superlative_match.group(2)
            options = [
                AmbiguityOption(
                    label=f"Rank by Total Monetary Spend (Revenue)",
                    interpretation=f"Identify {entity}s generating the highest total revenue ($).",
                    suggested_metric_id="revenue",
                ),
                AmbiguityOption(
                    label=f"Rank by Order Volume / Frequency",
                    interpretation=f"Identify {entity}s with the largest count of distinct completed orders.",
                    suggested_metric_id="order_count",
                ),
                AmbiguityOption(
                    label=f"Rank by Profit Margin Contribution",
                    interpretation=f"Identify {entity}s driving highest net gross profit ($).",
                    suggested_metric_id="profit",
                ),
            ]
            return AmbiguityResult(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.AMBIGUOUS_SUPERLATIVE,
                clarifying_question=(
                    f"You asked about the '{superlative_match.group(0)}'. How would you prefer to rank {entity}s?"
                ),
                options=options,
                candidate_metrics=[
                    self.catalog.get_metric("revenue"),
                    self.catalog.get_metric("order_count"),
                    self.catalog.get_metric("profit"),
                ],
                explanation=f"Ranking {entity}s can be calculated by monetary volume, transaction count, or profit margin.",
            )

        # 2. Check for Ambiguous Metric terms ("sales" -> revenue vs order volume)
        if re.search(r"\b(sales|performance|activity)\b", q_lower) and not re.search(r"\b(dollar|revenue|count|units|volume|amount)\b", q_lower):
            # Check if user specifically asked a vague question
            if any(phrase in q_lower for phrase in ["how are sales", "what are our sales", "sales numbers", "show me sales", "overall performance"]):
                options = [
                    AmbiguityOption(
                        label="Total Revenue ($)",
                        interpretation="Calculate total monetary sales volume in USD.",
                        suggested_metric_id="revenue",
                    ),
                    AmbiguityOption(
                        label="Total Orders (Volume)",
                        interpretation="Calculate the count of completed transaction orders.",
                        suggested_metric_id="order_count",
                    ),
                    AmbiguityOption(
                        label="Average Order Value (AOV)",
                        interpretation="Calculate mean revenue spent per transaction.",
                        suggested_metric_id="aov",
                    ),
                ]
                return AmbiguityResult(
                    is_ambiguous=True,
                    ambiguity_type=AmbiguityType.AMBIGUOUS_METRIC,
                    clarifying_question="The term 'sales' can refer to monetary revenue or transaction volume. Which definition would you like to view?",
                    options=options,
                    candidate_metrics=[
                        self.catalog.get_metric("revenue"),
                        self.catalog.get_metric("order_count"),
                        self.catalog.get_metric("aov"),
                    ],
                    explanation="Sales can be reported as dollar revenue, transaction volume, or average order value.",
                )

        # 3. Check for Missing Time Horizon on Period-Sensitive Metrics (Churn, Retention)
        is_churn_query = bool(re.search(r"\b(churn|retention|conversion rate)\b", q_lower))
        has_time_horizon = bool(
            re.search(
                r"\b(this month|last month|today|yesterday|this quarter|last quarter|year|q[1-4]|202[0-9]|january|february|march|april|may|june|july|august|september|october|november|december|between|since|last \d+ days)\b",
                q_lower,
            )
        )
        if is_churn_query and not has_time_horizon:
            metric_target = "churn" if "churn" in q_lower else ("retention" if "retention" in q_lower else "conversion rate")
            options = [
                AmbiguityOption(
                    label="Current Month (Month-to-Date)",
                    interpretation=f"Measure {metric_target} for the current active month.",
                    suggested_sql_clause="CURRENT_DATE",
                ),
                AmbiguityOption(
                    label="Trailing 30 Days (Rolling)",
                    interpretation=f"Measure {metric_target} over the last 30 consecutive calendar days.",
                ),
                AmbiguityOption(
                    label="Last Completed Quarter",
                    interpretation=f"Measure {metric_target} for the previous financial quarter.",
                ),
                AmbiguityOption(
                    label="All-Time Cumulative Cohort",
                    interpretation=f"Measure aggregate {metric_target} across all historical records.",
                ),
            ]
            return AmbiguityResult(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.MISSING_TIME_HORIZON,
                clarifying_question=f"{metric_target.capitalize()} depends on the evaluation period. Over which time horizon should this be computed?",
                options=options,
                candidate_metrics=[self.catalog.get_metric("customer_churn" if "churn" in q_lower else "retention")],
                explanation=f"{metric_target.capitalize()} requires a specified cohort time window for meaningful business comparison.",
            )

        # 4. Check for Multiple Conflicting Datasets
        if len(available_datasets) > 1 and not any(d.get("name", "").lower() in q_lower for d in available_datasets):
            # Check if datasets have similar schemas or could both answer the query
            names = [d.get("name", "Unnamed") for d in available_datasets]
            # If the user's question mentions general data without targeting a specific dataset
            if any(term in q_lower for term in ["revenue", "sales", "orders", "customers", "data"]) and len(names) >= 2:
                # If neither dataset is mentioned
                matching_count = sum(1 for d in available_datasets if any(c.get("name") in ["revenue", "amount", "sales"] for c in d.get("columns", [])))
                if matching_count > 1:
                    options = [
                        AmbiguityOption(
                            label=f"Dataset: {d.get('name')}",
                            interpretation=f"Run analysis on {d.get('name')} (Table: {d.get('table_name')})",
                        )
                        for d in available_datasets[:3]
                    ]
                    return AmbiguityResult(
                        is_ambiguous=True,
                        ambiguity_type=AmbiguityType.MULTIPLE_MATCHING_DATASETS,
                        clarifying_question="You have multiple datasets containing sales/revenue data. Which dataset should I inspect?",
                        options=options,
                        candidate_metrics=[self.catalog.get_metric("revenue")],
                        explanation="Multiple available data sources match this query.",
                    )

        # 5. Check for Missing Schema Metadata (preventing hallucinated joins / columns)
        # Scan if question asks for fields not present in any available dataset
        unsupported_fields = []
        if available_datasets:
            all_known_columns: Set[str] = set()
            for d in available_datasets:
                for c in d.get("columns", []):
                    col_name = c.get("name", "").lower() if isinstance(c, dict) else str(c).lower()
                    all_known_columns.add(col_name)

            # Check if user asks about specific entities absent from available data
            entity_checks = {
                "inventory": ["inventory", "stock", "warehouse", "shelf"],
                "shipping carrier": ["carrier", "tracking", "fedex", "ups", "dhl", "transit_time"],
                "nps / satisfaction": ["nps", "satisfaction_score", "survey", "rating"],
            }
            for entity_label, keywords in entity_checks.items():
                if any(kw in q_lower for kw in keywords):
                    if not any(kw in col for col in all_known_columns for kw in keywords):
                        unsupported_fields.append(entity_label)

            if unsupported_fields:
                missing_str = ", ".join(unsupported_fields)
                return AmbiguityResult(
                    is_ambiguous=True,
                    ambiguity_type=AmbiguityType.MISSING_SCHEMA_METADATA,
                    clarifying_question=(
                        f"Your question asks about {missing_str}, but no column or table covering {missing_str} exists in the connected datasets. "
                        f"Would you like to analyze related available columns ({', '.join(sorted(list(all_known_columns))[:6])}) instead?"
                    ),
                    options=[
                        AmbiguityOption(
                            label="Analyze Available Metrics",
                            interpretation=f"Proceed with existing dataset columns: {', '.join(sorted(list(all_known_columns))[:5])}",
                        ),
                        AmbiguityOption(
                            label="Upload New Data Source",
                            interpretation="Upload an additional CSV/Excel or connect a database containing the missing attributes.",
                        ),
                    ],
                    explanation=f"Cannot invent joins or synthetic attributes for missing business entity: {missing_str}.",
                )

        # Query is clear and actionable
        return AmbiguityResult(
            is_ambiguous=False,
            ambiguity_type=AmbiguityType.NONE,
        )
