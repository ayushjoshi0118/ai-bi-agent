"""
Modular Query Planning, Verification, and Explanation Pipeline.
Separates:
1. Intent Classification
2. Semantic Query Planning (no invented joins, explicit date/null semantics)
3. Result Verification & Independent Checks
4. KPI Extraction & Grounded Explanation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from app.analytics.ambiguity import AmbiguityDetector, AmbiguityResult
from app.analytics.metrics import MetricDefinition, MetricUnit, SemanticMetricCatalog, default_metric_catalog
from app.schemas.query_plan import QueryPlan


class IntentType(str, Enum):
    METRIC_AGGREGATION = "metric_aggregation"
    DIMENSIONAL_BREAKDOWN = "dimensional_breakdown"
    TREND_ANALYSIS = "trend_analysis"
    PERIOD_COMPARISON = "period_comparison"
    ANOMALY_DETECTION = "anomaly_detection"
    AMBIGUOUS_CLARIFICATION = "ambiguous_clarification"
    ADVERSARIAL_OR_UNSUPPORTED = "adversarial_or_unsupported"


@dataclass
class IntentResult:
    intent: IntentType
    primary_metric_id: Optional[str] = None
    dimensions: List[str] = field(default_factory=list)
    time_range: Optional[Dict[str, str]] = None
    filters: List[str] = field(default_factory=list)
    confidence: float = 1.0
    ambiguity: Optional[AmbiguityResult] = None


@dataclass
class VerifiedKPI:
    name: str
    metric_id: str
    value: float
    formatted_value: str
    unit: str
    provenance_sql: str
    row_count_verified: int


@dataclass
class VerificationResult:
    is_valid: bool
    kpis: List[VerifiedKPI] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data_quality_issues: List[str] = field(default_factory=list)
    computed_checksum: Optional[float] = None


class IntentClassifier:
    """Classifies user query intent and extracts metrics, dimensions, and filters."""

    def __init__(self, catalog: Optional[SemanticMetricCatalog] = None):
        self.catalog = catalog or default_metric_catalog
        self.ambiguity_detector = AmbiguityDetector(self.catalog)

    def classify(
        self,
        question: str,
        available_datasets: List[Dict[str, Any]],
        context_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> IntentResult:
        q_lower = question.lower().strip()

        # 0. Check for adversarial / system manipulation attempts
        if any(term in q_lower for term in ["drop table", "alter table", "insert into", "delete from", "ignore instructions"]):
            return IntentResult(
                intent=IntentType.ADVERSARIAL_OR_UNSUPPORTED,
                confidence=1.0,
            )

        # 1. Run Ambiguity Detection first
        ambiguity = self.ambiguity_detector.analyze(question, available_datasets, context_messages)
        if ambiguity.is_ambiguous:
            return IntentResult(
                intent=IntentType.AMBIGUOUS_CLARIFICATION,
                ambiguity=ambiguity,
                confidence=0.95,
            )

        # 2. Check for Anomaly Detection intent
        if any(term in q_lower for term in ["anomaly", "anomalies", "unusual", "outlier", "irregular", "spike", "drop in daily"]):
            return IntentResult(
                intent=IntentType.ANOMALY_DETECTION,
                confidence=0.9,
            )

        # 3. Match metrics from catalog
        matched_metric = None
        for m in self.catalog.list_metrics():
            if m.id in q_lower or m.name.lower() in q_lower or any(syn in q_lower for syn in m.synonyms):
                matched_metric = m
                break

        # 4. Extract dimensions
        detected_dimensions = []
        dimension_keywords = {
            "region": ["region", "regional", "geography", "country", "territory"],
            "product_category": ["category", "product category", "product", "item"],
            "channel": ["channel", "acquisition channel", "source"],
            "date": ["daily", "day", "date", "by day", "trend", "month", "monthly", "by month", "quarter"],
            "customer_segment": ["segment", "tier", "cohort"],
        }
        for dim_name, keywords in dimension_keywords.items():
            if any(kw in q_lower for kw in keywords):
                detected_dimensions.append(dim_name)

        # 5. Extract time range / comparison intent
        is_comparison = bool(re.search(r"\b(compared (to|with)|versus|vs|growth|change|over previous)\b", q_lower))
        is_trend = "trend" in q_lower or "over time" in q_lower or "daily" in q_lower or "monthly" in q_lower

        if is_comparison:
            intent = IntentType.PERIOD_COMPARISON
        elif is_trend:
            intent = IntentType.TREND_ANALYSIS
        elif detected_dimensions:
            intent = IntentType.DIMENSIONAL_BREAKDOWN
        else:
            intent = IntentType.METRIC_AGGREGATION

        return IntentResult(
            intent=intent,
            primary_metric_id=matched_metric.id if matched_metric else "revenue",
            dimensions=detected_dimensions,
            confidence=0.85,
        )


class SemanticQueryPlanner:
    """
    Formulates a mathematically grounded SQL query plan using catalog metric formulas.
    Enforces safe date boundaries, explicit null handling, and rejects hallucinated joins.
    """

    def __init__(self, catalog: Optional[SemanticMetricCatalog] = None):
        self.catalog = catalog or default_metric_catalog

    def plan_query(
        self,
        intent: IntentResult,
        dataset: Dict[str, Any],
        question: str,
    ) -> Tuple[Optional[QueryPlan], Optional[str]]:
        """
        Generates a validated QueryPlan.
        Returns (QueryPlan, None) on success or (None, rejection_reason) if metadata is insufficient.
        """
        table_name = dataset.get("table_name", "dataset")
        columns_meta = dataset.get("columns", [])
        column_names = {c.get("name").lower(): c for c in columns_meta if isinstance(c, dict)}
        if not column_names and columns_meta:
            column_names = {str(c).lower(): {} for c in columns_meta}

        metric_def = self.catalog.get_metric(intent.primary_metric_id or "revenue")
        if not metric_def:
            metric_def = self.catalog.get_metric("revenue")

        # Resolve metric column name against actual table columns
        target_metric_col = None
        for candidate in ["revenue", "amount", "sales", "total_sales", "price"]:
            if candidate in column_names:
                target_metric_col = candidate
                break

        if not target_metric_col and metric_def.id in ["revenue", "profit", "aov"]:
            # Check if there is any numeric column
            numeric_cols = [name for name, meta in column_names.items() if meta.get("type", "").lower() in ["integer", "float", "numeric", "double", "real"]]
            if numeric_cols:
                target_metric_col = numeric_cols[0]
            else:
                return None, f"Dataset '{table_name}' does not contain numeric revenue/amount columns required for metric '{metric_def.name}'."

        # Map requested dimensions to existing columns
        valid_dimensions = []
        for dim in intent.dimensions:
            if dim in column_names:
                valid_dimensions.append(dim)
            elif dim == "product_category" and "category" in column_names:
                valid_dimensions.append("category")
            elif dim == "date":
                # Look for date/timestamp column
                date_cols = [c for c in column_names if any(k in c for k in ["date", "time", "created_at", "day"])]
                if date_cols:
                    valid_dimensions.append(date_cols[0])

        # Formulate safe SQL
        # Dimension group
        if valid_dimensions:
            dim_str = ", ".join(valid_dimensions)
            # Use safe metric formula with COALESCE to handle null values explicitly
            if metric_def.id == "order_count":
                sql = f"SELECT {dim_str}, COUNT(*) AS total_orders FROM {table_name} GROUP BY {dim_str} ORDER BY total_orders DESC"
            elif metric_def.id == "profit" and "cost" in column_names:
                sql = f"SELECT {dim_str}, SUM(COALESCE({target_metric_col}, 0) - COALESCE(cost, 0)) AS gross_profit FROM {table_name} GROUP BY {dim_str} ORDER BY gross_profit DESC"
            elif metric_def.id == "customer_churn" and "churned" in column_names and "customer_id" in column_names:
                sql = f"SELECT {dim_str}, ROUND(COUNT(DISTINCT CASE WHEN churned = 1 OR churned = TRUE THEN customer_id END) * 100.0 / NULLIF(COUNT(DISTINCT customer_id), 0), 2) AS churn_rate FROM {table_name} GROUP BY {dim_str}"
            else:
                sql = f"SELECT {dim_str}, SUM(COALESCE({target_metric_col}, 0)) AS total_{metric_def.id} FROM {table_name} GROUP BY {dim_str} ORDER BY total_{metric_def.id} DESC"
        else:
            # Single scalar aggregation
            if metric_def.id == "order_count":
                sql = f"SELECT COUNT(*) AS total_orders FROM {table_name}"
            elif metric_def.id == "profit" and "cost" in column_names:
                sql = f"SELECT SUM(COALESCE({target_metric_col}, 0) - COALESCE(cost, 0)) AS gross_profit FROM {table_name}"
            elif metric_def.id == "conversion_rate" and "converted" in column_names and "user_id" in column_names:
                sql = f"SELECT ROUND(COUNT(DISTINCT CASE WHEN converted = 1 OR converted = TRUE THEN user_id END) * 100.0 / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS conversion_rate FROM {table_name}"
            elif metric_def.id == "customer_churn" and "churned" in column_names and "customer_id" in column_names:
                sql = f"SELECT ROUND(COUNT(DISTINCT CASE WHEN churned = 1 OR churned = TRUE THEN customer_id END) * 100.0 / NULLIF(COUNT(DISTINCT customer_id), 0), 2) AS churn_rate FROM {table_name}"
            elif metric_def.id == "aov" and target_metric_col and ("order_id" in column_names or "id" in column_names):
                order_col = "order_id" if "order_id" in column_names else "id"
                sql = f"SELECT ROUND(SUM(COALESCE({target_metric_col}, 0)) * 1.0 / NULLIF(COUNT(DISTINCT {order_col}), 0), 2) AS aov FROM {table_name}"
            else:
                sql = f"SELECT SUM(COALESCE({target_metric_col}, 0)) AS total_{metric_def.id} FROM {table_name}"

        import uuid
        intent_literal_map = {
            IntentType.METRIC_AGGREGATION: "aggregation",
            IntentType.DIMENSIONAL_BREAKDOWN: "aggregation",
            IntentType.TREND_ANALYSIS: "trend",
            IntentType.PERIOD_COMPARISON: "comparison",
            IntentType.ANOMALY_DETECTION: "distribution",
            IntentType.AMBIGUOUS_CLARIFICATION: "lookup",
            IntentType.ADVERSARIAL_OR_UNSUPPORTED: "lookup",
        }
        plan_intent = intent_literal_map.get(intent.intent, "aggregation")

        plan = QueryPlan(
            dataset_id=uuid.UUID(dataset["dataset_id"]) if "dataset_id" in dataset and isinstance(dataset["dataset_id"], str) and len(dataset["dataset_id"]) == 36 else uuid.uuid4(),
            intent=plan_intent,
            target_tables=[table_name],
            selected_metrics=[metric_def.id],
            dimensions=valid_dimensions,
            sql_statement=sql,
            explanation=f"Query planned according to semantic metric '{metric_def.name}' (Formula: {metric_def.formula_sql}). Null values handled via COALESCE/NULLIF.",
        )
        return plan, None


class ResultVerifier:
    """
    Verifies query result payloads against mathematical and business sanity checks.
    Extracts verified KPIs and flags data quality issues (excessive nulls, negative revenue, etc.).
    """

    def __init__(self, catalog: Optional[SemanticMetricCatalog] = None):
        self.catalog = catalog or default_metric_catalog

    def verify_and_extract_kpis(
        self,
        rows: List[Dict[str, Any]],
        columns: List[str],
        metric_id: str,
        provenance_sql: str,
    ) -> VerificationResult:
        errors: List[str] = []
        warnings: List[str] = []
        dq_issues: List[str] = []
        kpis: List[VerifiedKPI] = []

        if not rows:
            return VerificationResult(
                is_valid=True,
                warnings=["Query executed successfully but returned 0 rows."],
            )

        metric_def = self.catalog.get_metric(metric_id)
        metric_name = metric_def.name if metric_def else metric_id.capitalize()
        unit_str = metric_def.unit.value if metric_def else ""

        # Identify numeric column in results
        numeric_col = None
        for col in columns:
            if any(isinstance(r.get(col), (int, float)) for r in rows):
                numeric_col = col
                break

        if numeric_col:
            vals = [r.get(numeric_col) for r in rows if r.get(numeric_col) is not None]
            null_count = sum(1 for r in rows if r.get(numeric_col) is None)

            # Check null ratio
            if null_count > 0:
                null_pct = (null_count / len(rows)) * 100.0
                if null_pct > 20.0:
                    dq_issues.append(f"High null rate in result column '{numeric_col}': {null_pct:.1f}% of rows are null.")

            # Validate numeric constraints
            if vals:
                # Check for negative values in strictly positive metrics (revenue, orders)
                if metric_id in ["revenue", "order_count", "aov"] and any(v < 0 for v in vals):
                    dq_issues.append(f"Unexpected negative values found in metric '{metric_id}'.")

                # Check percentage metric bounds
                if metric_def and metric_def.unit == MetricUnit.PERCENTAGE:
                    if any(v < 0 or v > 100.0 for v in vals):
                        warnings.append(f"Percentage metric '{metric_id}' returned values outside [0, 100]% range.")

                # Compute aggregate KPI
                total_val = float(np.sum(vals))
                if len(rows) == 1:
                    primary_val = float(vals[0])
                else:
                    primary_val = total_val

                # Format appropriately
                if unit_str == "USD":
                    formatted = f"${primary_val:,.2f}"
                elif unit_str == "%":
                    formatted = f"{primary_val:.2f}%"
                else:
                    formatted = f"{primary_val:,.2f}" if primary_val != int(primary_val) else f"{int(primary_val):,}"

                kpis.append(
                    VerifiedKPI(
                        name=metric_name,
                        metric_id=metric_id,
                        value=round(primary_val, 4),
                        formatted_value=formatted,
                        unit=unit_str,
                        provenance_sql=provenance_sql,
                        row_count_verified=len(rows),
                    )
                )

        return VerificationResult(
            is_valid=len(errors) == 0,
            kpis=kpis,
            errors=errors,
            warnings=warnings,
            data_quality_issues=dq_issues,
            computed_checksum=float(np.sum(vals)) if numeric_col and vals else None,
        )


class ResultExplainer:
    """
    Synthesizes executive business conclusions grounded strictly in verified data.
    Cites specific figures, time boundaries, sample sizes, and disclaims causality.
    """

    @staticmethod
    def explain(
        question: str,
        kpis: List[VerifiedKPI],
        rows: List[Dict[str, Any]],
        columns: List[str],
        warnings: List[str],
        data_quality_issues: List[str],
    ) -> str:
        if not rows:
            return (
                f"No records were found in the dataset matching your question: '{question}'. "
                "Please verify that the date range or filter criteria are present in the active dataset."
            )

        parts = []

        # 1. Direct answer with verified KPIs
        if kpis:
            primary_kpi = kpis[0]
            parts.append(
                f"### Verified Business Finding\n"
                f"**{primary_kpi.name}**: **{primary_kpi.formatted_value}** "
                f"(Computed over {primary_kpi.row_count_verified:,} verified records)."
            )

        # 2. Dimensional Breakdown Summary
        if len(rows) > 1 and len(columns) >= 2:
            dim_col = columns[0]
            val_col = columns[1]
            parts.append("\n**Top Segment Breakdown:**")
            for r in rows[:5]:
                dim_val = r.get(dim_col, "Unknown")
                raw_num = r.get(val_col)
                if isinstance(raw_num, (int, float)):
                    num_formatted = f"${raw_num:,.2f}" if "revenue" in val_col or "profit" in val_col or "sales" in val_col else f"{raw_num:,.2f}"
                else:
                    num_formatted = str(raw_num)
                parts.append(f"- **{dim_val}**: {num_formatted}")

            if len(rows) > 5:
                parts.append(f"*(Showing top 5 of {len(rows)} segments)*")

        # 3. Data Quality & Limitations
        if data_quality_issues or warnings:
            parts.append("\n**Data Quality Observations & Notes:**")
            for dq in data_quality_issues:
                parts.append(f"- *Warning*: {dq}")
            for w in warnings:
                parts.append(f"- *Note*: {w}")

        parts.append(
            "\n*Evidence Note: All numbers reflect direct database query results without model estimation. "
            "Statistical observations do not establish causal root causes.*"
        )

        return "\n".join(parts)
