"""
Operational Metrics and Reliability Telemetry.
Tracks LLM latency, token volume, estimated costs, query execution durations,
queue depth, ingestion errors, report delivery outcomes, and security alert events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Dict, List, Optional
import numpy as np


class OperationalMetricsCollector:
    """
    Thread-safe operational telemetry and metrics aggregator.
    Provides structured JSON and Prometheus-compatible metrics.
    """

    _instance: Optional[OperationalMetricsCollector] = None
    _lock = threading.Lock()

    def __new__(cls) -> OperationalMetricsCollector:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_metrics()
            return cls._instance

    def _init_metrics(self) -> None:
        self.lock = threading.Lock()
        self.llm_latencies: List[float] = []
        self.query_durations: List[float] = []
        self.llm_input_tokens: int = 0
        self.llm_output_tokens: int = 0
        self.llm_cost_usd: float = 0.0

        self.report_outcomes: Dict[str, int] = {
            "completed": 0,
            "skipped_duplicate": 0,
            "skipped_overlap": 0,
            "failed": 0,
            "aborted_security_revoked": 0,
        }
        self.security_failures: Dict[str, int] = {
            "cross_tenant_attempt": 0,
            "membership_revoked": 0,
            "disallowed_sql": 0,
            "rate_limit_exceeded": 0,
        }
        self.ingestion_failures: int = 0
        self.queue_depth_gauge: int = 0

    def record_llm_request(
        self,
        duration_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        with self.lock:
            self.llm_latencies.append(duration_ms)
            if len(self.llm_latencies) > 1000:
                self.llm_latencies = self.llm_latencies[-1000:]
            self.llm_input_tokens += input_tokens
            self.llm_output_tokens += output_tokens
            self.llm_cost_usd += cost_usd

    def record_query(self, duration_ms: float) -> None:
        with self.lock:
            self.query_durations.append(duration_ms)
            if len(self.query_durations) > 1000:
                self.query_durations = self.query_durations[-1000:]

    def record_report_outcome(self, outcome: str) -> None:
        with self.lock:
            self.report_outcomes[outcome] = self.report_outcomes.get(outcome, 0) + 1

    def record_security_failure(self, failure_type: str) -> None:
        with self.lock:
            self.security_failures[failure_type] = self.security_failures.get(failure_type, 0) + 1

    def record_ingestion_failure(self) -> None:
        with self.lock:
            self.ingestion_failures += 1

    def set_queue_depth(self, depth: int) -> None:
        with self.lock:
            self.queue_depth_gauge = depth

    def get_summary(self) -> Dict[str, Any]:
        with self.lock:
            llm_p50 = float(np.percentile(self.llm_latencies, 50)) if self.llm_latencies else 0.0
            llm_p95 = float(np.percentile(self.llm_latencies, 95)) if self.llm_latencies else 0.0
            query_p50 = float(np.percentile(self.query_durations, 50)) if self.query_durations else 0.0
            query_p95 = float(np.percentile(self.query_durations, 95)) if self.query_durations else 0.0

            return {
                "llm": {
                    "request_count": len(self.llm_latencies),
                    "latency_p50_ms": round(llm_p50, 2),
                    "latency_p95_ms": round(llm_p95, 2),
                    "input_tokens_total": self.llm_input_tokens,
                    "output_tokens_total": self.llm_output_tokens,
                    "total_tokens": self.llm_input_tokens + self.llm_output_tokens,
                    "estimated_cost_usd": round(self.llm_cost_usd, 6),
                },
                "queries": {
                    "query_count": len(self.query_durations),
                    "duration_p50_ms": round(query_p50, 2),
                    "duration_p95_ms": round(query_p95, 2),
                },
                "workflows": {
                    "queue_depth": self.queue_depth_gauge,
                    "report_outcomes": self.report_outcomes,
                },
                "security": {
                    "security_failures": self.security_failures,
                },
                "data_quality": {
                    "ingestion_failures": self.ingestion_failures,
                },
            }

    def get_prometheus_metrics(self) -> str:
        s = self.get_summary()
        lines = [
            "# HELP bi_llm_requests_total Total count of LLM completions",
            "# TYPE bi_llm_requests_total counter",
            f"bi_llm_requests_total {s['llm']['request_count']}",
            f"bi_llm_input_tokens_total {s['llm']['input_tokens_total']}",
            f"bi_llm_output_tokens_total {s['llm']['output_tokens_total']}",
            f"bi_llm_cost_usd_total {s['llm']['estimated_cost_usd']}",
            f"bi_llm_latency_p50_ms {s['llm']['latency_p50_ms']}",
            f"bi_llm_latency_p95_ms {s['llm']['latency_p95_ms']}",
            f"bi_query_duration_p50_ms {s['queries']['duration_p50_ms']}",
            f"bi_query_duration_p95_ms {s['queries']['duration_p95_ms']}",
            f"bi_queue_depth {s['workflows']['queue_depth']}",
            f"bi_ingestion_failures_total {s['data_quality']['ingestion_failures']}",
        ]
        for outcome, cnt in s['workflows']['report_outcomes'].items():
            lines.append(f'bi_report_outcomes_total{{outcome="{outcome}"}} {cnt}')
        for fail_type, cnt in s['security']['security_failures'].items():
            lines.append(f'bi_security_failures_total{{type="{fail_type}"}} {cnt}')

        return "\n".join(lines) + "\n"


metrics_collector = OperationalMetricsCollector()
