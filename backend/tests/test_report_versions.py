"""
Tests for Report creation, versioning snapshots, and saved analyses persistence.
"""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.schemas.report import ReportCreate, ReportUpdate, SavedAnalysisCreate
from app.security.password import hash_password
from app.services.report_service import ReportService


@pytest.mark.asyncio
async def test_report_versioning_and_snapshot(db_session: AsyncSession):
    user = User(email="rep_user@example.com", password_hash=hash_password("Pass123!"), full_name="Report User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Report Org", slug=f"rep-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    # 1. Create Report
    create_req = ReportCreate(
        title="Q3 Sales Summary",
        description="Comprehensive quarterly sales report",
        config={"chart_type": "line", "time_bucket": "month"},
    )
    report = await ReportService.create_report(db_session, org.id, user.id, create_req)
    assert report.title == "Q3 Sales Summary"
    assert len(report.versions) == 1
    assert report.versions[0].version_number == 1
    assert report.versions[0].content["config"]["chart_type"] == "line"

    # 2. Update Report
    update_req = ReportUpdate(
        title="Q3 Sales & Profit Summary",
        config={"chart_type": "line", "time_bucket": "month", "show_profit": True},
    )
    updated_report = await ReportService.update_report(db_session, org.id, user.id, report.id, update_req)
    assert updated_report.title == "Q3 Sales & Profit Summary"
    assert len(updated_report.versions) == 2
    assert updated_report.versions[1].version_number == 2
    assert updated_report.versions[1].content["config"]["show_profit"] is True


@pytest.mark.asyncio
async def test_saved_analysis_lifecycle(db_session: AsyncSession):
    user = User(email="analysis_user@example.com", password_hash=hash_password("Pass123!"), full_name="Analysis User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Analysis Org", slug=f"analysis-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    analysis_req = SavedAnalysisCreate(
        title="High Margin Products",
        description="Products with margin > 40%",
        chart_config={"chart": "bar", "metric": "margin"},
    )
    analysis = await ReportService.create_saved_analysis(db_session, org.id, user.id, analysis_req)
    assert analysis.title == "High Margin Products"
    assert analysis.created_by == user.id
    assert analysis.user_id == user.id
    assert analysis.chart_config["chart"] == "bar"

    # List saved analyses
    analyses = await ReportService.list_saved_analyses(db_session, org.id)
    assert len(analyses) >= 1
    assert any(a.id == analysis.id for a in analyses)
