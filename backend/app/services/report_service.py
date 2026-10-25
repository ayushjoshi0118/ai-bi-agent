"""
Report and Saved Analysis management service.
Handles report generation, data snapshots, and reproducible versioning.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.query import QueryExecution
from app.models.report import Report, ReportStatus, ReportVersion, SavedAnalysis
from app.schemas.report import ReportCreate, ReportUpdate, SavedAnalysisCreate
from app.security.tenant_security import TenantSecurityManager
from app.services.audit_service import AuditService


class ReportService:
    @staticmethod
    async def create_saved_analysis(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, req: SavedAnalysisCreate
    ) -> SavedAnalysis:
        analysis = SavedAnalysis(
            org_id=org_id,
            created_by=user_id,
            title=req.title.strip(),
            description=req.description,
            conversation_id=req.conversation_id,
            analysis_data={
                "query_execution_id": str(req.query_execution_id) if req.query_execution_id else None,
                "chart_config": req.chart_config or {},
            },
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="analysis.save",
            resource_type="saved_analysis",
            resource_id=analysis.id,
            details={"title": req.title},
        )
        return analysis

    @staticmethod
    async def list_saved_analyses(db: AsyncSession, org_id: uuid.UUID) -> List[SavedAnalysis]:
        stmt = (
            select(SavedAnalysis)
            .where(SavedAnalysis.org_id == org_id)
            .order_by(SavedAnalysis.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_report(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, req: ReportCreate
    ) -> Report:
        report = Report(
            org_id=org_id,
            created_by=user_id,
            title=req.title.strip(),
            description=req.description,
            status=ReportStatus.DRAFT,
            config=req.config or {},
        )
        db.add(report)
        await db.flush()

        # Generate initial version 1 snapshot
        initial_version = ReportVersion(
            report_id=report.id,
            version_number=1,
            content={
                "config": report.config or {},
                "data_snapshot": {"created_at": datetime.now(timezone.utc).isoformat()},
            },
            change_summary="Initial version",
            created_by=user_id,
        )
        db.add(initial_version)
        await db.commit()
        await db.refresh(report, ["versions"])

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="report.create",
            resource_type="report",
            resource_id=report.id,
            details={"title": req.title},
        )
        return report

    @staticmethod
    async def list_reports(db: AsyncSession, org_id: uuid.UUID) -> List[Report]:
        stmt = (
            select(Report)
            .options(selectinload(Report.versions))
            .where(Report.org_id == org_id)
            .order_by(Report.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_report(db: AsyncSession, org_id: uuid.UUID, report_id: uuid.UUID) -> Report:
        stmt = (
            select(Report)
            .options(selectinload(Report.versions))
            .where(Report.id == report_id, Report.org_id == org_id)
        )
        res = await db.execute(stmt)
        report = res.scalar_one_or_none()
        if not report:
            # Check for cross-tenant attempt and log security audit event
            await TenantSecurityManager.verify_object_ownership(
                db=db,
                org_id=org_id,
                user_id=uuid.uuid4(),
                model_class=Report,
                object_id=report_id,
                resource_label="report",
            )
        return report

    @staticmethod
    async def update_report(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, report_id: uuid.UUID, req: ReportUpdate
    ) -> Report:
        report = await ReportService.get_report(db, org_id, report_id)
        if req.title is not None:
            report.title = req.title.strip()
        if req.description is not None:
            report.description = req.description
        if req.status is not None:
            report.status = req.status
        if req.config is not None:
            report.config = req.config
            # Create a new version when configuration updates
            latest_version_num = len(report.versions) if report.versions else 0
            new_version = ReportVersion(
                report_id=report.id,
                version_number=latest_version_num + 1,
                content={
                    "config": req.config,
                    "data_snapshot": {"updated_at": datetime.now(timezone.utc).isoformat()},
                },
                change_summary="Updated configuration",
                created_by=user_id,
            )
            db.add(new_version)

        await db.commit()
        await db.refresh(report, ["versions"])

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="report.update",
            resource_type="report",
            resource_id=report.id,
        )
        return report

    @staticmethod
    async def delete_report(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, report_id: uuid.UUID
    ) -> None:
        report = await ReportService.get_report(db, org_id, report_id)
        await db.delete(report)
        await db.commit()

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="report.delete",
            resource_type="report",
            resource_id=report_id,
        )
