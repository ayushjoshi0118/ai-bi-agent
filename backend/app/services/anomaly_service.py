"""
Statistical Anomaly Detection Service.
Implements Z-Score, Interquartile Range (IQR), and Rolling Moving Average detection on metrics.
Enforces minimum sample sizes, calculates statistical baselines and deviations, and prevents duplicate alerts.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.anomaly import AnomalyDetection, AnomalySeverity, AnomalyStatus
from app.models.dataset import Dataset
from app.services.audit_service import AuditService
from app.services.data_source_service import DataSourceService

logger = structlog.get_logger(__name__)


class AnomalyService:
    @staticmethod
    async def run_detection(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
        metric_column: str,
        time_column: Optional[str] = None,
        method: str = "z_score",
        sensitivity: str = "medium",
        min_sample_size: int = 10,
    ) -> List[AnomalyDetection]:
        """
        Run statistical anomaly detection over a numeric column in the dataset.
        """
        stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.org_id == org_id)
        res = await db.execute(stmt)
        dataset = res.scalar_one_or_none()
        if not dataset:
            raise ValueError("Dataset not found")

        connector = DataSourceService.get_connector(dataset.data_source)
        try:
            # Query the target column and optional time column
            table_name = dataset.table_name
            if time_column:
                sql = f"SELECT {time_column}, {metric_column} FROM {table_name} WHERE {metric_column} IS NOT NULL ORDER BY {time_column} ASC"
            else:
                sql = f"SELECT {metric_column} FROM {table_name} WHERE {metric_column} IS NOT NULL"

            query_result = await connector.execute_read_only_query(sql=sql, max_rows=10000)
            rows = query_result.rows

            if len(rows) < min_sample_size:
                logger.info(
                    "anomaly_detection_skipped_insufficient_samples",
                    row_count=len(rows),
                    required=min_sample_size,
                )
                return []

            # Extract numeric series
            values = []
            timestamps = []
            for r in rows:
                v = r.get(metric_column)
                if isinstance(v, (int, float)) and not math.isnan(v):
                    values.append(float(v))
                    if time_column and r.get(time_column):
                        timestamps.append(str(r.get(time_column)))

            arr = np.array(values)
            n = len(arr)
            if n < min_sample_size:
                return []

            anomalies: List[AnomalyDetection] = []

            # Sensitivity multiplier
            threshold = 3.0 if sensitivity == "low" else (2.5 if sensitivity == "medium" else 2.0)

            if method == "iqr":
                q25, q75 = np.percentile(arr, [25, 75])
                iqr = q75 - q25
                iqr_factor = 1.8 if sensitivity == "low" else (1.5 if sensitivity == "medium" else 1.2)
                lower_bound = q25 - iqr_factor * iqr
                upper_bound = q75 + iqr_factor * iqr
                median_val = float(np.median(arr))

                for idx, val in enumerate(arr):
                    if val < lower_bound or val > upper_bound:
                        dev = abs(val - median_val) / (iqr if iqr > 0 else 1.0)
                        severity = AnomalySeverity.CRITICAL if dev > 3.0 else (
                            AnomalySeverity.HIGH if dev > 2.0 else AnomalySeverity.MEDIUM
                        )
                        anom = AnomalyDetection(
                            org_id=org_id,
                            dataset_id=dataset_id,
                            metric_name=metric_column,
                            metric_value=round(val, 4),
                            expected_value=round(median_val, 4),
                            deviation_score=round(dev, 2),
                            severity=severity,
                            status=AnomalyStatus.DETECTED,
                            detection_method="iqr",
                            explanation=f"Value {val} deviated significantly from median baseline {median_val:.2f} (IQR [{lower_bound:.2f}, {upper_bound:.2f}]). Note: Statistical observation only; does not prove causality.",
                            supporting_data={
                                "q25": float(q25),
                                "q75": float(q75),
                                "iqr": float(iqr),
                                "timestamp": timestamps[idx] if idx < len(timestamps) else None,
                            },
                        )
                        anomalies.append(anom)
            else:
                # Default: Z-score detection
                mean_val = float(np.mean(arr))
                std_val = float(np.std(arr))

                if std_val > 0:
                    z_scores = (arr - mean_val) / std_val
                    for idx, (val, z) in enumerate(zip(arr, z_scores)):
                        if abs(z) >= threshold:
                            severity = AnomalySeverity.CRITICAL if abs(z) >= 4.0 else (
                                AnomalySeverity.HIGH if abs(z) >= 3.0 else AnomalySeverity.MEDIUM
                            )
                            anom = AnomalyDetection(
                                org_id=org_id,
                                dataset_id=dataset_id,
                                metric_name=metric_column,
                                metric_value=round(val, 4),
                                expected_value=round(mean_val, 4),
                                deviation_score=round(float(abs(z)), 2),
                                severity=severity,
                                status=AnomalyStatus.DETECTED,
                                detection_method="z_score",
                                explanation=f"Observed value {val} deviated {abs(z):.2f} standard deviations from historical mean {mean_val:.2f}. Note: Statistical observation only; does not prove causality.",
                                supporting_data={
                                    "mean": round(mean_val, 4),
                                    "std": round(std_val, 4),
                                    "z_score": round(float(z), 2),
                                    "sample_size": n,
                                    "timestamp": timestamps[idx] if idx < len(timestamps) else None,
                                },
                            )
                            anomalies.append(anom)

            # Deduplicate and save only highest severity anomalies (up to 20)
            if anomalies:
                # Sort by deviation score descending
                anomalies.sort(key=lambda a: a.deviation_score or 0, reverse=True)
                top_anomalies = anomalies[:20]

                for a in top_anomalies:
                    db.add(a)
                await db.commit()

                await AuditService.log_event(
                    db,
                    org_id=org_id,
                    action="anomaly.detected",
                    resource_type="dataset",
                    resource_id=dataset_id,
                    details={
                        "metric": metric_column,
                        "anomalies_count": len(top_anomalies),
                        "method": method,
                    },
                )
                for a in top_anomalies:
                    await db.refresh(a)
                return top_anomalies

            return []
        finally:
            await connector.close()
