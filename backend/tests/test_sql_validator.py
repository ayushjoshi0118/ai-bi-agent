"""
Unit tests for the SQL Safety Validator.
Verifies AST-based rejection of DDL, DML, multi-statement injection, and disallowed functions.
"""

import pytest
from app.services.sql_validator import SQLValidator


def test_valid_select_query():
    validator = SQLValidator(allowed_tables={"sales"})
    res = validator.validate("SELECT product_id, SUM(amount) AS total FROM sales GROUP BY product_id")
    assert res.is_valid is True
    assert len(res.errors) == 0
    assert "sales" in res.tables_referenced


def test_valid_cte_query():
    validator = SQLValidator(allowed_tables={"orders"})
    sql = """
    WITH regional_orders AS (
        SELECT region, order_id, amount FROM orders WHERE status = 'completed'
    )
    SELECT region, AVG(amount) FROM regional_orders GROUP BY region
    """
    res = validator.validate(sql)
    assert res.is_valid is True
    assert "orders" in res.tables_referenced
    # CTE itself shouldn't be required in allowed_tables
    assert "regional_orders" not in res.tables_referenced


def test_reject_multiple_statements():
    validator = SQLValidator(allowed_tables={"users"})
    res = validator.validate("SELECT * FROM users; DROP TABLE users;")
    assert res.is_valid is False
    assert any("Multiple SQL statements" in err for err in res.errors)


def test_reject_ddl_drop():
    validator = SQLValidator()
    res = validator.validate("DROP TABLE transactions")
    assert res.is_valid is False
    assert any("strictly forbidden" in err for err in res.errors)


def test_reject_dml_insert_update_delete():
    validator = SQLValidator(allowed_tables={"accounts"})
    assert validator.validate("INSERT INTO accounts (id) VALUES (1)").is_valid is False
    assert validator.validate("UPDATE accounts SET balance = 0").is_valid is False
    assert validator.validate("DELETE FROM accounts WHERE 1=1").is_valid is False


def test_reject_dangerous_functions():
    validator = SQLValidator(allowed_tables={"metrics"})
    res = validator.validate("SELECT pg_sleep(10) FROM metrics")
    assert res.is_valid is False
    assert any("Disallowed function" in err for err in res.errors)

    res2 = validator.validate("SELECT pg_read_file('/etc/passwd') FROM metrics")
    assert res2.is_valid is False


def test_reject_select_into():
    validator = SQLValidator(allowed_tables={"sales"})
    res = validator.validate("SELECT * INTO new_sales FROM sales")
    assert res.is_valid is False
    assert any("SELECT INTO" in err for err in res.errors)


def test_reject_unauthorized_tables():
    validator = SQLValidator(allowed_tables={"public_data"})
    res = validator.validate("SELECT * FROM confidential_salaries")
    assert res.is_valid is False
    assert any("Access to table 'confidential_salaries' is prohibited" in err for err in res.errors)
