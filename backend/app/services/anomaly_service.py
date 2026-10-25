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
from sqlalchemy.orm import selectinload
import structlog

from app.analytics.anomaly import AdvancedAnomalyDetector, AnomalyMethod
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
        method: str = "mad",
        sensitivity: str = "medium",
        min_sample_size: int = 10,
    ) -> List[AnomalyDetection]:
        """
        Run statistical anomaly detection over a numeric column in the dataset.
        Supports MAD, Rolling Baseline, Seasonal Comparison, Z-Score, and IQR.
        """
        stmt = (
            select(Dataset)
            .options(selectinload(Dataset.data_source))
            .where(Dataset.id == dataset_id, Dataset.org_id == org_id)
        )
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
                else:
                    values.append(None)
                    if time_column:
                        timestamps.append(str(r.get(time_column)) if r.get(time_column) else None)

            # Map method string to AnomalyMethod enum
            method_clean = method.lower().strip()
            if method_clean in ("mad", "median_absolute_deviation"):
                chosen_method = AnomalyMethod.MAD
            elif method_clean in ("rolling", "rolling_baseline", "moving_average"):
                chosen_method = AnomalyMethod.ROLLING_BASELINE
            elif method_clean in ("seasonal", "seasonal_comparison", "week_over_week"):
                chosen_method = AnomalyMethod.SEASONAL_COMPARISON
            elif method_clean in ("iqr", "interquartile"):
                chosen_method = AnomalyMethod.IQR
            else:
                chosen_method = AnomalyMethod.Z_SCORE

            diag_result = AdvancedAnomalyDetector.detect(
                values=values,
                timestamps=timestamps if time_column else None,
                metric_name=metric_column,
                method=chosen_method,
                sensitivity=sensitivity,
            )

            if diag_result.insufficient_data_reason:
                logger.info(
                    "anomaly_detection_insufficient_data",
                    reason=diag_result.insufficient_data_reason,
                )
                return []

            anomalies: List[AnomalyDetection] = []
            now_utc = datetime.now(timezone.utc)

            for finding in diag_result.anomalies:
                sev_map = {
                    "low": AnomalySeverity.LOW,
                    "medium": AnomalySeverity.MEDIUM,
                    "high": AnomalySeverity.HIGH,
                    "critical": AnomalySeverity.CRITICAL,
                }
                sev = sev_map.get(finding.severity.value, AnomalySeverity.MEDIUM)

                anom = AnomalyDetection(
                    org_id=org_id,
                    dataset_id=dataset_id,
                    metric_name=metric_column,
                    metric_value=finding.observed_value,
                    expected_range_low=finding.lower_bound,
                    expected_range_high=finding.upper_bound,
                    severity=sev,
                    status=AnomalyStatus.DETECTED,
                    description=finding.explanation,
                    detection_metadata={
                        "expected_value": finding.expected_value,
                        "deviation_score": finding.deviation_score,
                        "method": finding.method.value,
                        "timestamp": finding.timestamp,
                        "sample_size": finding.sample_size,
                        "supporting_evidence": finding.supporting_evidence,
                        "causal_disclaimer": finding.causal_disclaimer,
                    },
                    detected_at=now_utc,
                )
                anomalies.append(anom)

            # Deduplicate and save only highest severity anomalies (up to 20)
            if anomalies:
                # Sort by deviation score descending
                anomalies.sort(
                    key=lambda a: (a.detection_metadata or {}).get("deviation_score", 0),
                    reverse=True,
                )
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
                        "method": chosen_method.value,
                        "dq_warnings_count": len(diag_result.data_quality_warnings),
                    },
                )
                for a in top_anomalies:
                    await db.refresh(a)
                return top_anomalies

            return []
        finally:
            await connector.close()
