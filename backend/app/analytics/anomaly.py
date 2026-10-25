"""
Advanced Anomaly Detection and Data Quality Diagnostics Engine.
Implements:
1. Median Absolute Deviation (MAD) - robust to extreme outliers
2. Robust Rolling Baselines - tracks moving windows and detects structural level shifts
3. Seasonal Comparisons - evaluates day-of-week and week-over-week seasonal residuals
4. Standard Z-Score and Interquartile Range (IQR)
5. Separation of Data Quality Warnings from Business Metric Anomalies
6. Strict Sample-Size Requirements and Explicit Non-Causal Disclaimers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class AnomalyMethod(str, Enum):
    MAD = "mad"
    ROLLING_BASELINE = "rolling_baseline"
    SEASONAL_COMPARISON = "seasonal_comparison"
    Z_SCORE = "z_score"
    IQR = "iqr"


class AnomalyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyFinding:
    metric_name: str
    observed_value: float
    expected_value: float
    deviation_score: float
    severity: AnomalyLevel
    method: AnomalyMethod
    timestamp: Optional[str] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    sample_size: int = 0
    time_range: Optional[str] = None
    explanation: str = ""
    supporting_evidence: Dict[str, Any] = field(default_factory=dict)
    is_data_quality_issue: bool = False
    causal_disclaimer: str = (
        "Statistical observation only. Correlation does not imply causation, "
        "and statistical deviation does not constitute definitive proof of a business defect."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "deviation_score": self.deviation_score,
            "severity": self.severity.value,
            "method": self.method.value,
            "timestamp": self.timestamp,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "sample_size": self.sample_size,
            "time_range": self.time_range,
            "explanation": self.explanation,
            "supporting_evidence": self.supporting_evidence,
            "is_data_quality_issue": self.is_data_quality_issue,
            "causal_disclaimer": self.causal_disclaimer,
        }


@dataclass
class DataQualityWarning:
    warning_type: str
    description: str
    affected_column: str
    severity: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticsResult:
    anomalies: List[AnomalyFinding] = field(default_factory=list)
    data_quality_warnings: List[DataQualityWarning] = field(default_factory=list)
    method_used: str = ""
    sample_size: int = 0
    insufficient_data_reason: Optional[str] = None


class AdvancedAnomalyDetector:
    """
    Production-grade statistical diagnostics and anomaly detection engine.
    """

    MIN_SAMPLES_STANDARD = 10
    MIN_SAMPLES_ROLLING = 14
    MIN_SAMPLES_SEASONAL = 21

    @classmethod
    def detect(
        cls,
        values: List[float],
        timestamps: Optional[List[str]] = None,
        metric_name: str = "metric",
        method: AnomalyMethod = AnomalyMethod.MAD,
        sensitivity: str = "medium",  # "low", "medium", "high"
        seasonal_period: int = 7,     # 7 for daily data with weekly seasonality
        rolling_window: int = 7,
    ) -> DiagnosticsResult:
        result = DiagnosticsResult(method_used=method.value)

        # 1. First run Data Quality Screening
        dq_warnings = cls._check_data_quality(values, timestamps, metric_name)
        result.data_quality_warnings = dq_warnings

        # Clean NaN and infinite values
        valid_pairs = []
        for idx, v in enumerate(values):
            if v is not None and not math.isnan(v) and not math.isinf(v):
                ts = timestamps[idx] if timestamps and idx < len(timestamps) else None
                valid_pairs.append((float(v), ts))

        if not valid_pairs:
            result.insufficient_data_reason = "No valid numeric observations available for analysis."
            return result

        clean_vals = np.array([p[0] for p in valid_pairs])
        clean_ts = [p[1] for p in valid_pairs]
        n = len(clean_vals)
        result.sample_size = n

        # Check sample size threshold based on method
        min_required = cls.MIN_SAMPLES_STANDARD
        if method == AnomalyMethod.ROLLING_BASELINE:
            min_required = cls.MIN_SAMPLES_ROLLING
        elif method == AnomalyMethod.SEASONAL_COMPARISON:
            min_required = cls.MIN_SAMPLES_SEASONAL

        if n < min_required:
            result.insufficient_data_reason = (
                f"Insufficient historical data: method '{method.value}' requires at least {min_required} observations, "
                f"but only {n} valid points were provided."
            )
            return result

        # 2. Execute selected statistical algorithm
        if method == AnomalyMethod.MAD:
            anomalies = cls._detect_mad(clean_vals, clean_ts, metric_name, sensitivity)
        elif method == AnomalyMethod.ROLLING_BASELINE:
            anomalies = cls._detect_rolling(clean_vals, clean_ts, metric_name, sensitivity, window=rolling_window)
        elif method == AnomalyMethod.SEASONAL_COMPARISON:
            anomalies = cls._detect_seasonal(clean_vals, clean_ts, metric_name, sensitivity, period=seasonal_period)
        elif method == AnomalyMethod.IQR:
            anomalies = cls._detect_iqr(clean_vals, clean_ts, metric_name, sensitivity)
        else:
            anomalies = cls._detect_zscore(clean_vals, clean_ts, metric_name, sensitivity)

        result.anomalies = anomalies
        return result

    @classmethod
    def _check_data_quality(
        cls,
        raw_values: List[Optional[float]],
        timestamps: Optional[List[str]],
        metric_name: str,
    ) -> List[DataQualityWarning]:
        """Separates data quality warnings from business anomalies."""
        warnings: List[DataQualityWarning] = []
        total = len(raw_values)
        if total == 0:
            return warnings

        # Null Spike Check
        null_count = sum(1 for v in raw_values if v is None or (isinstance(v, float) and math.isnan(v)))
        null_rate = (null_count / total) * 100.0
        if null_rate > 10.0:
            warnings.append(
                DataQualityWarning(
                    warning_type="high_null_rate",
                    description=f"High missing observation rate: {null_rate:.1f}% of values in '{metric_name}' are NULL/NaN.",
                    affected_column=metric_name,
                    severity="high" if null_rate > 30.0 else "medium",
                    details={"null_count": null_count, "total_count": total, "null_pct": round(null_rate, 2)},
                )
            )

        # Duplicate Timestamp Check
        if timestamps and len(timestamps) > 1:
            unique_ts = set(timestamps)
            if len(unique_ts) < len(timestamps):
                dupe_count = len(timestamps) - len(unique_ts)
                warnings.append(
                    DataQualityWarning(
                        warning_type="duplicate_timestamps",
                        description=f"Duplicate timestamps detected: {dupe_count} duplicate time points found in time series.",
                        affected_column="timestamp",
                        severity="medium",
                        details={"duplicate_count": dupe_count},
                    )
                )

        # Negative Values in Non-Negative Metric Check
        numeric_vals = [v for v in raw_values if isinstance(v, (int, float)) and not math.isnan(v)]
        if metric_name.lower() in ["revenue", "sales", "amount", "orders", "users", "count"]:
            neg_count = sum(1 for v in numeric_vals if v < 0)
            if neg_count > 0:
                warnings.append(
                    DataQualityWarning(
                        warning_type="negative_values_found",
                        description=f"Negative values found in strictly non-negative business metric '{metric_name}' ({neg_count} records).",
                        affected_column=metric_name,
                        severity="high",
                        details={"negative_count": neg_count},
                    )
                )

        return warnings

    @classmethod
    def _detect_mad(
        cls,
        vals: np.ndarray,
        timestamps: List[Optional[str]],
        metric_name: str,
        sensitivity: str,
    ) -> List[AnomalyFinding]:
        """
        Median Absolute Deviation (MAD):
        Median M = median(X)
        MAD = median(|X - M|)
        Modified Z = 0.6745 * |X - M| / MAD
        Robust against extreme outliers.
        """
        median = float(np.median(vals))
        abs_diff = np.abs(vals - median)
        mad = float(np.median(abs_diff))

        # Sensitivity thresholds
        threshold = 3.5 if sensitivity == "low" else (3.0 if sensitivity == "medium" else 2.5)

        findings: List[AnomalyFinding] = []
        if mad == 0:
            # All or almost all values are identical
            mad = float(np.mean(abs_diff)) if np.mean(abs_diff) > 0 else 1.0

        mod_z_scores = 0.6745 * (vals - median) / mad

        for idx, (val, z) in enumerate(zip(vals, mod_z_scores)):
            if abs(z) >= threshold:
                sev = AnomalyLevel.CRITICAL if abs(z) >= 5.0 else (
                    AnomalyLevel.HIGH if abs(z) >= 4.0 else AnomalyLevel.MEDIUM
                )
                ts = timestamps[idx] if idx < len(timestamps) else None
                direction = "spike above" if z > 0 else "drop below"
                findings.append(
                    AnomalyFinding(
                        metric_name=metric_name,
                        observed_value=round(float(val), 4),
                        expected_value=round(median, 4),
                        deviation_score=round(float(abs(z)), 2),
                        severity=sev,
                        method=AnomalyMethod.MAD,
                        timestamp=ts,
                        lower_bound=round(median - (threshold * mad / 0.6745), 2),
                        upper_bound=round(median + (threshold * mad / 0.6745), 2),
                        sample_size=len(vals),
                        explanation=(
                            f"Value {val:,.2f} represents an unusual {direction} historical median baseline "
                            f"of {median:,.2f} (MAD deviation: {abs(z):.2f})."
                        ),
                        supporting_evidence={
                            "median_baseline": round(median, 4),
                            "mad": round(mad, 4),
                            "modified_z_score": round(float(z), 2),
                            "threshold": threshold,
                        },
                    )
                )

        findings.sort(key=lambda a: a.deviation_score, reverse=True)
        return findings

    @classmethod
    def _detect_rolling(
        cls,
        vals: np.ndarray,
        timestamps: List[Optional[str]],
        metric_name: str,
        sensitivity: str,
        window: int = 7,
    ) -> List[AnomalyFinding]:
        """
        Robust Rolling Baseline:
        Computes rolling median and rolling IQR across a sliding window of past observations.
        Detects sudden step-changes or localized spikes relative to recent trajectory.
        """
        threshold = 3.0 if sensitivity == "low" else (2.5 if sensitivity == "medium" else 2.0)
        findings: List[AnomalyFinding] = []
        n = len(vals)

        for i in range(window, n):
            window_vals = vals[max(0, i - window):i]
            local_median = float(np.median(window_vals))
            local_iqr = float(np.percentile(window_vals, 75) - np.percentile(window_vals, 25))
            scale = local_iqr if local_iqr > 0 else float(np.std(window_vals))
            if scale == 0:
                scale = 1.0

            cur_val = vals[i]
            dev = (cur_val - local_median) / scale

            if abs(dev) >= threshold:
                sev = AnomalyLevel.CRITICAL if abs(dev) >= 4.0 else (
                    AnomalyLevel.HIGH if abs(dev) >= 3.0 else AnomalyLevel.MEDIUM
                )
                ts = timestamps[i] if i < len(timestamps) else None
                direction = "surge" if dev > 0 else "drop"
                findings.append(
                    AnomalyFinding(
                        metric_name=metric_name,
                        observed_value=round(float(cur_val), 4),
                        expected_value=round(local_median, 4),
                        deviation_score=round(float(abs(dev)), 2),
                        severity=sev,
                        method=AnomalyMethod.ROLLING_BASELINE,
                        timestamp=ts,
                        lower_bound=round(local_median - threshold * scale, 2),
                        upper_bound=round(local_median + threshold * scale, 2),
                        sample_size=window,
                        explanation=(
                            f"Localized {direction}: observed value {cur_val:,.2f} deviated by {abs(dev):.2f}x "
                            f"from trailing {window}-period rolling median baseline of {local_median:,.2f}."
                        ),
                        supporting_evidence={
                            "rolling_window_size": window,
                            "trailing_median": round(local_median, 4),
                            "trailing_scale": round(scale, 4),
                        },
                    )
                )

        findings.sort(key=lambda a: a.deviation_score, reverse=True)
        return findings

    @classmethod
    def _detect_seasonal(
        cls,
        vals: np.ndarray,
        timestamps: List[Optional[str]],
        metric_name: str,
        sensitivity: str,
        period: int = 7,
    ) -> List[AnomalyFinding]:
        """
        Seasonal Comparison:
        Calculates week-over-week (or cycle-over-cycle) residuals:
        Delta_t = X_t - X_{t - period}
        Evaluates residual deviation against seasonal baseline.
        """
        threshold = 3.0 if sensitivity == "low" else (2.5 if sensitivity == "medium" else 2.0)
        findings: List[AnomalyFinding] = []
        n = len(vals)

        residuals = []
        indices = []
        for i in range(period, n):
            delta = vals[i] - vals[i - period]
            residuals.append(delta)
            indices.append(i)

        if not residuals:
            return findings

        res_arr = np.array(residuals)
        res_median = float(np.median(res_arr))
        res_mad = float(np.median(np.abs(res_arr - res_median)))
        if res_mad == 0:
            res_mad = float(np.std(res_arr)) if np.std(res_arr) > 0 else 1.0

        for r_idx, delta in enumerate(residuals):
            original_idx = indices[r_idx]
            z = 0.6745 * (delta - res_median) / res_mad
            if abs(z) >= threshold:
                observed = vals[original_idx]
                seasonal_prior = vals[original_idx - period]
                ts = timestamps[original_idx] if original_idx < len(timestamps) else None
                prior_ts = timestamps[original_idx - period] if original_idx - period < len(timestamps) else None
                sev = AnomalyLevel.CRITICAL if abs(z) >= 4.0 else (
                    AnomalyLevel.HIGH if abs(z) >= 3.0 else AnomalyLevel.MEDIUM
                )
                findings.append(
                    AnomalyFinding(
                        metric_name=metric_name,
                        observed_value=round(float(observed), 4),
                        expected_value=round(float(seasonal_prior), 4),
                        deviation_score=round(float(abs(z)), 2),
                        severity=sev,
                        method=AnomalyMethod.SEASONAL_COMPARISON,
                        timestamp=ts,
                        sample_size=n,
                        explanation=(
                            f"Seasonal deviation: value of {observed:,.2f} differed significantly from equivalent "
                            f"prior seasonal cycle baseline of {seasonal_prior:,.2f} (Cycle lag: {period} periods)."
                        ),
                        supporting_evidence={
                            "seasonal_period": period,
                            "prior_cycle_value": round(float(seasonal_prior), 4),
                            "prior_timestamp": prior_ts,
                            "residual_delta": round(float(delta), 4),
                        },
                    )
                )

        findings.sort(key=lambda a: a.deviation_score, reverse=True)
        return findings

    @classmethod
    def _detect_iqr(
        cls,
        vals: np.ndarray,
        timestamps: List[Optional[str]],
        metric_name: str,
        sensitivity: str,
    ) -> List[AnomalyFinding]:
        q25, q75 = np.percentile(vals, [25, 75])
        iqr = float(q75 - q25)
        median = float(np.median(vals))
        factor = 1.8 if sensitivity == "low" else (1.5 if sensitivity == "medium" else 1.2)
        lower_bound = q25 - factor * iqr
        upper_bound = q75 + factor * iqr

        findings: List[AnomalyFinding] = []
        for idx, val in enumerate(vals):
            if val < lower_bound or val > upper_bound:
                dev = abs(val - median) / (iqr if iqr > 0 else 1.0)
                sev = AnomalyLevel.CRITICAL if dev > 3.0 else (
                    AnomalyLevel.HIGH if dev > 2.0 else AnomalyLevel.MEDIUM
                )
                ts = timestamps[idx] if idx < len(timestamps) else None
                findings.append(
                    AnomalyFinding(
                        metric_name=metric_name,
                        observed_value=round(float(val), 4),
                        expected_value=round(median, 4),
                        deviation_score=round(float(dev), 2),
                        severity=sev,
                        method=AnomalyMethod.IQR,
                        timestamp=ts,
                        lower_bound=round(float(lower_bound), 2),
                        upper_bound=round(float(upper_bound), 2),
                        sample_size=len(vals),
                        explanation=f"Value {val:,.2f} lies outside IQR bounds [{lower_bound:,.2f}, {upper_bound:,.2f}].",
                        supporting_evidence={"q25": round(float(q25), 4), "q75": round(float(q75), 4), "iqr": round(iqr, 4)},
                    )
                )
        findings.sort(key=lambda a: a.deviation_score, reverse=True)
        return findings

    @classmethod
    def _detect_zscore(
        cls,
        vals: np.ndarray,
        timestamps: List[Optional[str]],
        metric_name: str,
        sensitivity: str,
    ) -> List[AnomalyFinding]:
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        threshold = 3.0 if sensitivity == "low" else (2.5 if sensitivity == "medium" else 2.0)
        findings: List[AnomalyFinding] = []
        if std == 0:
            return findings

        z_scores = (vals - mean) / std
        for idx, (val, z) in enumerate(zip(vals, z_scores)):
            if abs(z) >= threshold:
                sev = AnomalyLevel.CRITICAL if abs(z) >= 4.0 else (
                    AnomalyLevel.HIGH if abs(z) >= 3.0 else AnomalyLevel.MEDIUM
                )
                ts = timestamps[idx] if idx < len(timestamps) else None
                findings.append(
                    AnomalyFinding(
                        metric_name=metric_name,
                        observed_value=round(float(val), 4),
                        expected_value=round(mean, 4),
                        deviation_score=round(float(abs(z)), 2),
                        severity=sev,
                        method=AnomalyMethod.Z_SCORE,
                        timestamp=ts,
                        lower_bound=round(mean - threshold * std, 2),
                        upper_bound=round(mean + threshold * std, 2),
                        sample_size=len(vals),
                        explanation=f"Value {val:,.2f} deviated {abs(z):.2f} standard deviations from mean {mean:,.2f}.",
                        supporting_evidence={"mean": round(mean, 4), "std": round(std, 4), "z_score": round(float(z), 2)},
                    )
                )
        findings.sort(key=lambda a: a.deviation_score, reverse=True)
        return findings
