"""
Tests for CSV safety, column sanitization, and formula injection handling.
"""

from __future__ import annotations

import os
import tempfile
import pytest

from app.connectors.csv_connector import CSVConnector


@pytest.mark.asyncio
async def test_csv_with_special_characters_and_whitespace_in_columns():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
        f.write("User Name,Total Revenue ($),Tax %,Order-ID\n")
        f.write("Alice,1000.50,10.0,ORD-001\n")
        f.write("Bob,2500.00,12.5,ORD-002\n")
        f_path = f.name

    try:
        connector = CSVConnector(file_path=f_path, table_name="test_orders")
        ok, msg = await connector.test_connection()
        assert ok is True

        schema = await connector.get_table_schema("test_orders")
        col_names = [c.name for c in schema]
        # Verify columns are sanitized to clean SQL identifiers
        assert "user_name" in col_names
        assert "total_revenue" in col_names or "total_revenue__" in col_names
        assert "tax" in col_names or "tax__" in col_names
        assert "order_id" in col_names

        # Execute read-only query
        result = await connector.execute_read_only_query("SELECT user_name, order_id FROM test_orders")
        assert result.row_count == 2
        assert result.rows[0]["user_name"] == "Alice"
        assert result.rows[1]["user_name"] == "Bob"
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)
        if os.path.exists(f"{f_path}.db"):
            os.remove(f"{f_path}.db")


@pytest.mark.asyncio
async def test_csv_formula_injection_defense():
    """
    Ensure cells containing spreadsheet formula injection strings (e.g. =cmd|' /C calc'!A0)
    are stored as literal strings without evaluation.
    """
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
        f.write("id,formula_input,amount\n")
        f.write("1,=cmd|' /C calc'!A0,100\n")
        f.write("2,+cmd|' /C notepad'!A0,200\n")
        f.write("3,@SUM(1+1),300\n")
        f_path = f.name

    try:
        connector = CSVConnector(file_path=f_path, table_name="malicious_formulas")
        ok, _ = await connector.test_connection()
        assert ok is True

        result = await connector.execute_read_only_query("SELECT formula_input, amount FROM malicious_formulas")
        assert result.row_count == 3
        # Values must remain strictly literal string data
        assert result.rows[0]["formula_input"] == "=cmd|' /C calc'!A0"
        assert result.rows[1]["formula_input"] == "+cmd|' /C notepad'!A0"
        assert result.rows[2]["formula_input"] == "@SUM(1+1)"
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)
        if os.path.exists(f"{f_path}.db"):
            os.remove(f"{f_path}.db")


@pytest.mark.asyncio
async def test_csv_empty_file_handling():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
        f.write("")  # Empty file
        f_path = f.name

    try:
        connector = CSVConnector(file_path=f_path, table_name="empty_test")
        ok, msg = await connector.test_connection()
        # Should gracefully fail without unhandled exception
        assert ok is False
        assert "Failed to parse CSV" in msg
    finally:
        if os.path.exists(f_path):
            os.remove(f_path)
        if os.path.exists(f"{f_path}.db"):
            os.remove(f"{f_path}.db")
