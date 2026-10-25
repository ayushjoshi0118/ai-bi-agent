"""
Deterministic Synthetic Benchmark Dataset Generator.
Generates mathematically verifiable e-commerce and SaaS datasets with known ground-truth metrics,
pre-calculated totals, injected anomalies, and controlled null/edge cases.
"""

from __future__ import annotations

import csv
import io
import math
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd


class SyntheticBenchmarkData:
    """
    Produces deterministic test datasets with known mathematical ground truth.
    Used for automated regression testing, metric verification, and evaluation gates.
    """

    # Ground truth constants
    TOTAL_ROWS = 600
    TOTAL_REVENUE = 300000.00
    TOTAL_COST = 180000.00
    GROSS_PROFIT = 120000.00
    GROSS_MARGIN_PCT = 40.00
    TOTAL_CUSTOMERS = 300
    CHURNED_CUSTOMERS = 36
    CHURN_RATE_PCT = 12.00
    CONVERSION_SESSIONS = 500
    CONVERTED_SESSIONS = 40
    CONVERSION_RATE_PCT = 8.00
    ANOMALY_DATE = "2026-02-14"
    ANOMALY_REVENUE = 100.00  # Injected severe drop from daily ~5,000 baseline

    @classmethod
    def generate_benchmark_records(cls) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generates 600 deterministic records across 60 days (10 orders per day).
        Returns (records_list, ground_truth_dict).
        """
        np.random.seed(42)  # Strictly deterministic
        records: List[Dict[str, Any]] = []

        regions = ["North", "South", "East", "West"]
        categories = ["Electronics", "Apparel", "Home Goods"]

        # 60 days from 2026-01-01 to 2026-03-01
        days = pd.date_range(start="2026-01-01", periods=60, freq="D")
        order_idx = 1001
        user_idx = 2001

        # We will distribute exact revenue ($300,000) across the 600 rows:
        # Base daily revenue = $5,000 across 10 orders (~$500 per order)
        # Day 45 (2026-02-14) is injected anomaly: $100 total ($10 per order)
        # Remaining 59 days share $299,900 (~$5,083.05 per day)

        # Baseline per normal order:
        normal_daily_total = 299900.0 / 59.0
        normal_order_rev = normal_daily_total / 10.0
        normal_order_cost = normal_order_rev * 0.60  # 40% margin

        anomaly_order_rev = 10.0
        anomaly_order_cost = 6.0

        for day_num, day_ts in enumerate(days):
            day_str = day_ts.strftime("%Y-%m-%d")
            is_anomaly_day = (day_str == cls.ANOMALY_DATE)

            for order_in_day in range(10):
                reg = regions[order_in_day % len(regions)]
                cat = categories[order_in_day % len(categories)]

                if is_anomaly_day:
                    rev = anomaly_order_rev
                    cst = anomaly_order_cost
                else:
                    # Deterministic small variation maintaining exact day total
                    jitter = ((order_in_day - 4.5) * 20.0)
                    rev = normal_order_rev + jitter
                    cst = rev * 0.60

                # Customer mapping (300 distinct customers)
                c_id = f"CUST_{(order_idx % 300) + 1:04d}"
                # 36 customers churned (cust 1 to 36)
                cust_num = (order_idx % 300) + 1
                is_churned = 1 if cust_num <= 36 else 0

                # 40 conversions out of 500 user sessions
                is_converted = 1 if (order_idx % 15 == 0 and order_idx <= 1600) else 0

                record = {
                    "order_id": f"ORD_{order_idx}",
                    "date": day_str,
                    "region": reg,
                    "category": cat,
                    "customer_id": c_id,
                    "user_id": f"USER_{(order_idx % 500) + 1:04d}",
                    "revenue": round(rev, 2),
                    "cost": round(cst, 2),
                    "churned": is_churned,
                    "converted": is_converted,
                    "status": "completed",
                }
                records.append(record)
                order_idx += 1

        # Adjust any rounding discrepancy on the last normal record to ensure exact penny precision
        total_rev_calc = sum(r["revenue"] for r in records)
        diff_rev = round(cls.TOTAL_REVENUE - total_rev_calc, 2)
        if abs(diff_rev) > 0:
            records[0]["revenue"] = round(records[0]["revenue"] + diff_rev, 2)
            records[0]["cost"] = round(records[0]["revenue"] * 0.60, 2)

        ground_truth = {
            "total_revenue": cls.TOTAL_REVENUE,
            "total_cost": cls.TOTAL_COST,
            "gross_profit": cls.GROSS_PROFIT,
            "gross_margin_pct": cls.GROSS_MARGIN_PCT,
            "total_orders": len(records),
            "distinct_customers": len(set(r["customer_id"] for r in records)),
            "churn_rate_pct": cls.CHURN_RATE_PCT,
            "conversion_rate_pct": cls.CONVERSION_RATE_PCT,
            "anomaly_date": cls.ANOMALY_DATE,
            "anomaly_observed_daily_revenue": cls.ANOMALY_REVENUE,
            "normal_daily_revenue_baseline": round(normal_daily_total, 2),
        }

        return records, ground_truth

    @classmethod
    def generate_csv_bytes(cls) -> Tuple[bytes, Dict[str, Any]]:
        records, ground_truth = cls.generate_benchmark_records()
        output = io.StringIO()
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue().encode("utf-8"), ground_truth
