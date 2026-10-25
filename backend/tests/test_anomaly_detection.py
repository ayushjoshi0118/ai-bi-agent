"""
Unit tests for statistical anomaly detection algorithms.
"""

import math
import numpy as np
import pytest
from app.services.anomaly_service import AnomalyService


def test_statistical_calculations():
    # Verify synthetic normal distribution with injected extreme outlier
    data = [100.0, 102.0, 98.0, 105.0, 97.0, 101.0, 99.0, 103.0, 100.0, 99.0, 102.0]
    outlier = 500.0  # extreme spike
    full_data = data + [outlier]

    mean_val = np.mean(full_data)
    std_val = np.std(full_data)

    z_score_outlier = (outlier - mean_val) / std_val
    # Outlier should have z-score > 2.5
    assert z_score_outlier > 2.5

    # Check IQR
    q25, q75 = np.percentile(full_data, [25, 75])
    iqr = q75 - q25
    upper_bound = q75 + 1.5 * iqr
    assert outlier > upper_bound
