# Semantic Metrics, Ambiguity Detection, and Evaluation Framework

## 1. Executive Summary

This document specifies the business metric governance, semantic query planning, statistical anomaly detection, and automated evaluation framework implemented for the AI Business Intelligence Agent.

The platform eliminates hallucinated SQL and unverified claims through:
1. **Explicit Semantic Metric Catalog**: Formulas, dimensions, units, owners, filter criteria, and divide-by-zero protection.
2. **Ambiguity Detection**: Interactive clarification whenever user prompts lack required time horizons, metrics, or ranking dimensions.
3. **Multi-Method Anomaly Detection**: Median Absolute Deviation (MAD), Rolling Baselines, and Seasonal Comparisons.
4. **Data Quality Separation**: Flagging missing observations and data anomalies separately from business deviations.
5. **Deterministic Benchmark Suite**: Version-controlled evaluation with 16 test cases against mathematical ground truth.

---

## 2. Semantic Metric Catalog

All business queries map to formal definitions in `SemanticMetricCatalog` ([`backend/app/analytics/metrics.py`](file:///c:/Users/ayush/Dropbox/PC%20(2)/Downloads/BI%20Agent/backend/app/analytics/metrics.py)):

| Metric ID | Metric Name | Standard SQL Formula | Unit | Owner | Applicable Filters |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `revenue` | Total Net Revenue | `SUM(COALESCE(revenue, amount, 0))` | USD | Finance Operations | `status != 'cancelled'`, `status != 'refunded'` |
| `profit` | Gross Profit | `SUM(COALESCE(revenue, 0) - COALESCE(cost, 0))` | USD | Corporate Finance | `status = 'completed'` |
| `conversion_rate` | Conversion Rate | `COUNT(DISTINCT conversions) * 100.0 / NULLIF(COUNT(DISTINCT sessions), 0)` | % | Growth Analytics | `is_bot = FALSE` |
| `customer_churn` | Customer Churn Rate | `COUNT(DISTINCT churned_users) * 100.0 / NULLIF(COUNT(DISTINCT initial_users), 0)` | % | Customer Success | `status IN ('active', 'churned')` |
| `retention` | Customer Retention Rate | `COUNT(DISTINCT retained_users) * 100.0 / NULLIF(COUNT(DISTINCT cohort_users), 0)` | % | Customer Success | Cohort active records |
| `aov` | Average Order Value | `SUM(revenue) * 1.0 / NULLIF(COUNT(DISTINCT order_id), 0)` | USD | E-Commerce Analytics | `status = 'completed'` |
| `gross_margin` | Gross Margin % | `SUM(revenue - cost) * 100.0 / NULLIF(SUM(revenue), 0)` | % | Corporate Finance | `revenue > 0` |
| `order_count` | Total Order Volume | `COUNT(DISTINCT order_id)` | count | Operations | All completed transactions |

---

## 3. Ambiguity Detection & Clarification

Rather than making silent assumptions or inventing metrics, the `AmbiguityDetector` ([`backend/app/analytics/ambiguity.py`](file:///c:/Users/ayush/Dropbox/PC%20(2)/Downloads/BI%20Agent/backend/app/analytics/ambiguity.py)) checks:

1. **Vague Metric Names**: Questions asking about "sales" trigger an explicit choice between Total Revenue ($), Order Count (Volume), or Average Order Value (AOV).
2. **Ambiguous Superlatives**: Questions asking for "top customer" or "best product" ask whether to rank by Revenue ($), Order Frequency, or Gross Margin contribution.
3. **Missing Time Horizons**: Rate metrics (churn, retention) without explicit date boundaries prompt for specific cohort windows (Current Month, Rolling 30 Days, Last Quarter).
4. **Missing Schema Attributes**: Prompts asking about data not present in connected tables (e.g., shipping transit times, warehouse inventory) refuse to invent tables and offer available columns instead.

---

## 4. Multi-Method Statistical Anomaly Detection

The `AdvancedAnomalyDetector` ([`backend/app/analytics/anomaly.py`](file:///c:/Users/ayush/Dropbox/PC%20(2)/Downloads/BI%20Agent/backend/app/analytics/anomaly.py)) supports 5 detection methodologies:

1. **Median Absolute Deviation (MAD)**:
   $$\text{MAD} = \text{median}(|X - \text{median}(X)|)$$
   $$\text{Modified } Z = 0.6745 \cdot \frac{X - \text{median}(X)}{\text{MAD}}$$
   Robust against extreme outliers that skew normal mean and standard deviation.
2. **Robust Rolling Baseline**: Tracks moving window (default: 7 periods) medians and IQRs to identify localized shifts and sudden baseline drops.
3. **Seasonal Comparisons**: Computes week-over-week (lag 7) or cycle residuals to evaluate deviations against recurring weekly patterns.
4. **Standard Z-Score & IQR**: High-speed statistical baselines for normally distributed metrics.
5. **Data Quality Separation**: Null spikes (> 10% nulls), duplicate timestamps, and negative revenue values are flagged as `DataQualityWarning` items distinct from business anomalies.
6. **Non-Causal Disclaimer**: Every finding includes the mandatory notice:
   *"Statistical observation only. Correlation does not imply causation, and statistical deviation does not constitute definitive proof of a business defect."*

---

## 5. Ground-Truth Synthetic Dataset & Automated Regression Gate

Evaluation is automated via `EvaluationRunner` ([`backend/app/evaluation/evaluator.py`](file:///c:/Users/ayush/Dropbox/PC%20(2)/Downloads/BI%20Agent/backend/app/evaluation/evaluator.py)):
- **Synthetic Dataset**: 600 records across 60 days with known ground truths:
  - Total Revenue: $300,000.00
  - Total Cost: $180,000.00
  - Gross Profit: $120,000.00 (Margin: 40.0%)
  - Total Orders: 600
  - Distinct Customers: 300
  - Churned Customers: 36 (Churn Rate: 12.00%)
  - Injected Revenue Drop Anomaly: 2026-02-14 (Observed: $100.00 vs normal baseline ~$5,083.05).
