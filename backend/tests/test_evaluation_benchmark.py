"""
Automated Evaluation Benchmark & Regression Gates.
Runs versioned benchmark cases against deterministic ground truth.
Verifies semantic metric calculations, ambiguity detection, anomaly detection,
refusal behaviors, and enforces accuracy regression thresholds.
"""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd

from app.analytics.metrics import SemanticMetricCatalog, default_metric_catalog, MetricUnit
from app.analytics.ambiguity import AmbiguityDetector, AmbiguityType
from app.analytics.anomaly import AdvancedAnomalyDetector, AnomalyMethod, AnomalyLevel
from app.analytics.pipeline import (
    IntentClassifier,
    IntentType,
    SemanticQueryPlanner,
    ResultVerifier,
    ResultExplainer,
)
from app.evaluation.evaluator import EvaluationRunner
from app.evaluation.synthetic_data import SyntheticBenchmarkData


# ==============================================================================
# 1. Semantic Metric Catalog Tests
# ==============================================================================

def test_semantic_metric_catalog_standard_definitions():
    catalog = default_metric_catalog
    revenue = catalog.get_metric("revenue")
    profit = catalog.get_metric("profit")
    churn = catalog.get_metric("customer_churn")
    cvr = catalog.get_metric("conversion_rate")
    retention = catalog.get_metric("retention")
    aov = catalog.get_metric("aov")

    assert revenue is not None
    assert revenue.unit == MetricUnit.CURRENCY_USD
    assert "COALESCE" in revenue.formula_sql
    assert "status != 'cancelled'" in revenue.applicable_filters

    assert profit is not None
    assert "cost" in profit.formula_sql.lower()
    assert profit.unit == MetricUnit.CURRENCY_USD

    assert churn is not None
    assert churn.unit == MetricUnit.PERCENTAGE
    assert "NULLIF" in churn.formula_sql  # Divide-by-zero protection

    assert cvr is not None
    assert cvr.unit == MetricUnit.PERCENTAGE
    assert "NULLIF" in cvr.formula_sql

    assert retention is not None
    assert retention.unit == MetricUnit.PERCENTAGE

    assert aov is not None
    assert aov.unit == MetricUnit.CURRENCY_USD


def test_metric_catalog_offline_compute_functions():
    catalog = default_metric_catalog
    df = pd.DataFrame({
        "revenue": [100.0, 200.0, 300.0],
        "cost": [60.0, 110.0, 150.0],
        "order_id": ["O1", "O2", "O3"],
        "customer_id": ["C1", "C2", "C3"],
        "churned": [0, 1, 0],
    })

    rev_metric = catalog.get_metric("revenue")
    profit_metric = catalog.get_metric("profit")
    churn_metric = catalog.get_metric("customer_churn")
    aov_metric = catalog.get_metric("aov")

    assert rev_metric.compute_fn(df) == 600.0
    assert profit_metric.compute_fn(df) == 280.0
    assert round(churn_metric.compute_fn(df), 2) == 33.33
    assert aov_metric.compute_fn(df) == 200.0


# ==============================================================================
# 2. Ambiguity Detection & Clarification Tests
# ==============================================================================

def test_detect_ambiguous_sales_metric():
    detector = AmbiguityDetector()
    datasets = [{"name": "Sales 2026", "table_name": "sales", "columns": [{"name": "revenue"}, {"name": "orders"}]}]

    res = detector.analyze("What are our sales numbers?", datasets)
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.AMBIGUOUS_METRIC
    assert len(res.options) >= 2
    assert any("Revenue" in opt.label for opt in res.options)
    assert any("Orders" in opt.label for opt in res.options)


def test_detect_ambiguous_superlative():
    detector = AmbiguityDetector()
    datasets = [{"name": "Orders", "table_name": "orders", "columns": [{"name": "customer_id"}, {"name": "revenue"}]}]

    res = detector.analyze("Who is our best customer?", datasets)
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.AMBIGUOUS_SUPERLATIVE
    assert "best customer" in res.clarifying_question.lower()
    assert len(res.options) >= 2


def test_detect_missing_time_horizon_for_churn():
    detector = AmbiguityDetector()
    datasets = [{"name": "Subscriptions", "table_name": "subs", "columns": [{"name": "churned"}, {"name": "date"}]}]

    res = detector.analyze("Show me our customer churn rate.", datasets)
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.MISSING_TIME_HORIZON
    assert "time horizon" in res.clarifying_question.lower()


def test_detect_missing_metadata_no_invented_joins():
    detector = AmbiguityDetector()
    # Dataset only contains orders, no carrier or inventory columns
    datasets = [{"name": "Orders", "table_name": "orders", "columns": [{"name": "revenue"}, {"name": "order_id"}]}]

    res = detector.analyze("Show me shipment carrier delivery times.", datasets)
    assert res.is_ambiguous is True
    assert res.ambiguity_type == AmbiguityType.MISSING_SCHEMA_METADATA
    assert "shipping carrier" in res.clarifying_question


# ==============================================================================
# 3. Advanced Anomaly Detection Tests
# ==============================================================================

def test_anomaly_detection_mad_identifies_injected_drop():
    # 30 days normal baseline of ~1000, day 20 dropped to 50
    np.random.seed(42)
    vals = [1000.0 + np.random.normal(0, 20) for _ in range(30)]
    vals[20] = 50.0  # Injected severe drop
    timestamps = [f"2026-01-{i+1:02d}" for i in range(30)]

    diag = AdvancedAnomalyDetector.detect(
        values=vals,
        timestamps=timestamps,
        metric_name="revenue",
        method=AnomalyMethod.MAD,
    )

    assert len(diag.anomalies) >= 1
    top = diag.anomalies[0]
    assert top.timestamp == "2026-01-21"
    assert top.observed_value == 50.0
    assert top.expected_value > 950.0
    assert top.deviation_score > 3.0
    assert "Correlation does not imply causation" in top.causal_disclaimer


def test_anomaly_detection_rolling_baseline():
    # 25 days: first 15 days around 100, then sudden spike to 500 at day 16
    vals = [100.0] * 15 + [500.0] + [100.0] * 9
    timestamps = [f"day_{i+1}" for i in range(25)]

    diag = AdvancedAnomalyDetector.detect(
        values=vals,
        timestamps=timestamps,
        metric_name="active_users",
        method=AnomalyMethod.ROLLING_BASELINE,
        rolling_window=7,
    )

    assert len(diag.anomalies) >= 1
    assert diag.anomalies[0].timestamp == "day_16"
    assert diag.anomalies[0].observed_value == 500.0


def test_anomaly_detection_seasonal_comparison():
    # 28 days with weekly cycle: weekend spikes
    vals = []
    for day in range(28):
        base = 200.0 if (day % 7) in (5, 6) else 50.0
        vals.append(base)
    # Day 21 (normal weekday = 50) spikes unexpectedly to 400
    vals[21] = 400.0
    timestamps = [f"2026-02-{i+1:02d}" for i in range(28)]

    diag = AdvancedAnomalyDetector.detect(
        values=vals,
        timestamps=timestamps,
        metric_name="signups",
        method=AnomalyMethod.SEASONAL_COMPARISON,
        seasonal_period=7,
    )

    assert len(diag.anomalies) >= 1
    assert diag.anomalies[0].timestamp == "2026-02-22"


def test_anomaly_detection_insufficient_samples_warning():
    # Only 5 samples (below 10 threshold)
    vals = [10.0, 20.0, 15.0, 18.0, 12.0]
    diag = AdvancedAnomalyDetector.detect(values=vals, method=AnomalyMethod.MAD)
    assert diag.insufficient_data_reason is not None
    assert "requires at least" in diag.insufficient_data_reason


def test_anomaly_detection_data_quality_screening():
    # Contains high nulls (30% null) and negative revenue
    vals = [100.0, None, -50.0, 200.0, None, 150.0, None, 180.0, 210.0, 190.0]
    diag = AdvancedAnomalyDetector.detect(values=vals, metric_name="revenue")
    assert len(diag.data_quality_warnings) >= 2
    types = [w.warning_type for w in diag.data_quality_warnings]
    assert "high_null_rate" in types
    assert "negative_values_found" in types


# ==============================================================================
# 4. Result Verifier & Explainer Tests
# ==============================================================================

def test_result_verifier_extracts_kpis():
    verifier = ResultVerifier(default_metric_catalog)
    rows = [{"region": "North", "total_revenue": 150000.0}, {"region": "South", "total_revenue": 150000.0}]
    cols = ["region", "total_revenue"]

    res = verifier.verify_and_extract_kpis(rows, cols, "revenue", "SELECT region, SUM(revenue) FROM orders")
    assert res.is_valid is True
    assert len(res.kpis) == 1
    assert res.kpis[0].value == 300000.0
    assert res.kpis[0].formatted_value == "$300,000.00"
    assert res.kpis[0].unit == "USD"


def test_result_explainer_formatting():
    verifier = ResultVerifier(default_metric_catalog)
    rows = [{"region": "North", "total_revenue": 150000.0}, {"region": "South", "total_revenue": 150000.0}]
    v_res = verifier.verify_and_extract_kpis(rows, ["region", "total_revenue"], "revenue", "SELECT ...")

    explanation = ResultExplainer.explain(
        question="What was total revenue by region?",
        kpis=v_res.kpis,
        rows=rows,
        columns=["region", "total_revenue"],
        warnings=[],
        data_quality_issues=[],
    )

    assert "Total Net Revenue" in explanation
    assert "$300,000.00" in explanation
    assert "North" in explanation
    assert "South" in explanation
    assert "Correlation does not imply causation" in explanation or "Statistical observations do not establish causal root causes" in explanation


# ==============================================================================
# 5. Full Evaluation Benchmark & Regression Gates
# ==============================================================================

def test_evaluation_runner_regression_gate():
    """
    Executes the versioned benchmark suite and asserts strict regression gates.
    """
    report = EvaluationRunner.run_suite()

    # Log summary for evaluation report traceability
    print(f"\n--- EVALUATION BENCHMARK RESULTS ({report.version}) ---")
    print(f"Total Cases: {report.total_cases}")
    print(f"Passed Cases: {report.passed_cases}")
    print(f"Overall Pass Rate: {report.overall_pass_rate_pct:.1f}%")
    print(f"SQL Validity Rate: {report.sql_validity_rate_pct:.1f}%")
    print(f"Exact Metric Accuracy: {report.exact_metric_accuracy_pct:.1f}%")
    print(f"Ambiguity Clarification Rate: {report.ambiguity_clarification_rate_pct:.1f}%")
    print(f"Security Refusal Rate: {report.security_refusal_rate_pct:.1f}%")
    print(f"Metadata Refusal Rate: {report.metadata_refusal_rate_pct:.1f}%")
    print(f"Anomaly Detection Pass Rate: {report.anomaly_detection_pass_rate_pct:.1f}%")
    print(f"Latency P50: {report.latency_p50_ms:.2f}ms | P95: {report.latency_p95_ms:.2f}ms")
    print(f"Estimated Cost: ${report.estimated_cost_usd:.6f}")

    # Enforce regression gates
    assert report.overall_pass_rate_pct >= 90.0, f"Overall pass rate {report.overall_pass_rate_pct}% fell below 90% threshold"
    assert report.sql_validity_rate_pct == 100.0, f"SQL validity {report.sql_validity_rate_pct}% fell below 100%"
    assert report.exact_metric_accuracy_pct == 100.0, f"Exact metric accuracy {report.exact_metric_accuracy_pct}% fell below 100%"
    assert report.security_refusal_rate_pct == 100.0, f"Security refusal rate {report.security_refusal_rate_pct}% fell below 100%"
    assert report.ambiguity_clarification_rate_pct == 100.0, f"Ambiguity clarification {report.ambiguity_clarification_rate_pct}% fell below 100%"
    assert report.metadata_refusal_rate_pct == 100.0, f"Metadata refusal {report.metadata_refusal_rate_pct}% fell below 100%"
    assert report.anomaly_detection_pass_rate_pct == 100.0, f"Anomaly detection {report.anomaly_detection_pass_rate_pct}% fell below 100%"
