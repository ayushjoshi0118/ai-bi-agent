"""
Evaluation Benchmark & Ground-Truth Test Harness.
"""

from app.evaluation.benchmark_cases import (
    BENCHMARK_CASES,
    BENCHMARK_SUITE_VERSION,
    BenchmarkCase,
    BenchmarkCategory,
    ExpectedOutcome,
)
from app.evaluation.evaluator import (
    BenchmarkReport,
    CaseEvaluationResult,
    EvaluationRunner,
)
from app.evaluation.synthetic_data import SyntheticBenchmarkData

__all__ = [
    "BENCHMARK_CASES",
    "BENCHMARK_SUITE_VERSION",
    "BenchmarkCase",
    "BenchmarkCategory",
    "ExpectedOutcome",
    "BenchmarkReport",
    "CaseEvaluationResult",
    "EvaluationRunner",
    "SyntheticBenchmarkData",
]
