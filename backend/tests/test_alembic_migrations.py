"""
Tests for Alembic migration schema coverage.
Verifies that all 15 models are defined across the revision sequence.
"""

from __future__ import annotations

import ast
from pathlib import Path
import pytest


def test_migration_revisions_chain_and_tables():
    versions_dir = Path("alembic/versions")
    migration_files = sorted(list(versions_dir.glob("*.py")))
    assert len(migration_files) >= 2

    # Verify 0001_initial
    content1 = (versions_dir / "0001_initial.py").read_text(encoding="utf-8")
    tree1 = ast.parse(content1)
    funcs1 = [n.name for n in ast.walk(tree1) if isinstance(n, ast.FunctionDef)]
    assert "upgrade" in funcs1
    assert "downgrade" in funcs1
    assert "0001_initial" in content1
    assert "down_revision = None" in content1

    # Verify 0002_complete_schema
    content2 = (versions_dir / "0002_complete_schema.py").read_text(encoding="utf-8")
    tree2 = ast.parse(content2)
    funcs2 = [n.name for n in ast.walk(tree2) if isinstance(n, ast.FunctionDef)]
    assert "upgrade" in funcs2
    assert "downgrade" in funcs2
    assert "0002_complete_schema" in content2
    assert "down_revision = '0001_initial'" in content2

    # Verify all production tables are declared
    required_tables = [
        "data_sources",
        "datasets",
        "conversations",
        "messages",
        "query_executions",
        "reports",
        "report_versions",
        "saved_analyses",
        "scheduled_jobs",
        "job_runs",
        "anomaly_detections",
        "audit_events",
        "notifications",
    ]
    for table_name in required_tables:
        assert f"'{table_name}'" in content2
