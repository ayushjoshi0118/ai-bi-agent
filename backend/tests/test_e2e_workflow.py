"""
End-to-end integration test:
Upload CSV -> Auto-profile Schema -> AI Question -> SQL Validation -> Execution -> Chart Generation.
"""

import os
import tempfile
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import OrgRole
from app.services.ai_orchestrator import AIOrchestrator
from app.services.ingestion_service import IngestionService


@pytest.mark.asyncio
async def test_full_bi_e2e_workflow(client: AsyncClient, db_session: AsyncSession, test_user, test_org):
    # 1. Prepare sample business CSV dataset
    csv_content = (
        "region,product,revenue,transactions,date\n"
        "North,Widget A,15000,120,2026-01-01\n"
        "South,Widget A,8000,65,2026-01-01\n"
        "East,Widget B,22000,190,2026-01-01\n"
        "West,Widget B,17500,140,2026-01-01\n"
        "North,Widget B,19000,150,2026-02-01\n"
        "South,Widget B,9500,75,2026-02-01\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tf:
        tf.write(csv_content)
        temp_csv_path = tf.name

    try:
        from fastapi import UploadFile

        with open(temp_csv_path, "rb") as f:
            upload_file = UploadFile(
                file=f,
                filename="regional_sales.csv",
                headers={"content-type": "text/csv"},
            )

            # Ingest file
            data_source, dataset = await IngestionService.ingest_file(
                db=db_session,
                org_id=test_org.id,
                user_id=test_user.id,
                upload_file=upload_file,
                dataset_name="Regional Sales 2026",
            )

        assert dataset.name == "Regional Sales 2026"
        assert dataset.row_count == 6
        assert len(dataset.schema_metadata["columns"]) == 5

        # 2. Ask question to AI agent
        result = await AIOrchestrator.analyze(
            db=db_session,
            org_id=test_org.id,
            user_id=test_user.id,
            question="What was total revenue by region?",
            dataset_ids=[dataset.id],
        )

        assert "conversation_id" in result
        assert "answer" in result
        assert len(result["queries"]) >= 1
        query_info = result["queries"][0]
        assert query_info["row_count"] > 0
        assert result["chart"] is not None
        assert "data" in result["chart"]

    finally:
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        sqlite_db = f"{temp_csv_path}.db"
        if os.path.exists(sqlite_db):
            os.remove(sqlite_db)
