"""
Data source management service with credential encryption and connector factory.
"""

from __future__ import annotations

import json
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors.base import BaseConnector
from app.connectors.csv_connector import CSVConnector
from app.connectors.postgres import PostgresConnector
from app.connectors.xlsx_connector import XLSXConnector
from app.models.data_source import DataSource, DataSourceStatus, DataSourceType
from app.models.dataset import Dataset
from app.schemas.data_source import DataSourceCreate, PostgresConnectionConfig
from app.security.encryption import decrypt_value, encrypt_value
from app.services.audit_service import AuditService


class DataSourceService:
    @staticmethod
    def get_connector(data_source: DataSource) -> BaseConnector:
        """Instantiate a connector instance for the given DataSource with decrypted credentials."""
        if data_source.source_type == DataSourceType.POSTGRESQL:
            if not data_source.encrypted_credentials:
                raise ValueError("Missing encrypted credentials for PostgreSQL data source")
            creds_str = decrypt_value(data_source.encrypted_credentials)
            creds = json.loads(creds_str)
            config = data_source.connection_config or {}
            return PostgresConnector(
                host=creds.get("host") or config.get("host", "localhost"),
                port=int(creds.get("port") or config.get("port", 5432)),
                database=creds.get("database") or config.get("database", "postgres"),
                user=creds.get("username") or creds.get("user", "postgres"),
                password=creds.get("password", ""),
                schema=config.get("schema", "public"),
                ssl=config.get("ssl", False),
            )
        elif data_source.source_type == DataSourceType.CSV:
            config = data_source.connection_config or {}
            file_path = config.get("file_path")
            if not file_path:
                raise ValueError("CSV data source missing file path in connection_config")
            return CSVConnector(file_path=file_path, table_name=config.get("table_name", "dataset"))
        elif data_source.source_type == DataSourceType.XLSX:
            config = data_source.connection_config or {}
            file_path = config.get("file_path")
            if not file_path:
                raise ValueError("XLSX data source missing file path in connection_config")
            return XLSXConnector(
                file_path=file_path,
                table_name=config.get("table_name", "dataset"),
                sheet_name=config.get("sheet_name"),
            )
        else:
            raise ValueError(f"Unsupported data source type: {data_source.source_type}")

    @staticmethod
    async def create_postgres_source(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        config: PostgresConnectionConfig,
    ) -> DataSource:
        # Separate sensitive credentials to encrypt
        creds_dict = {
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "username": config.username,
            "password": config.password,
        }
        encrypted = encrypt_value(json.dumps(creds_dict))

        # Public connection metadata (NO PASSWORD)
        safe_config = {
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "username": config.username,
            "schema": config.schema_name,
            "ssl": config.ssl,
        }

        source = DataSource(
            org_id=org_id,
            created_by=user_id,
            name=name.strip(),
            source_type=DataSourceType.POSTGRESQL,
            encrypted_credentials=encrypted,
            connection_config=safe_config,
            status=DataSourceStatus.PENDING,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="datasource.create",
            resource_type="data_source",
            resource_id=source.id,
            details={"type": "postgresql", "name": name},
        )
        return source

    @staticmethod
    async def test_source_connection(
        db: AsyncSession, org_id: uuid.UUID, source_id: uuid.UUID
    ) -> tuple[bool, str]:
        stmt = select(DataSource).where(DataSource.id == source_id, DataSource.org_id == org_id)
        res = await db.execute(stmt)
        source = res.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

        try:
            connector = DataSourceService.get_connector(source)
            try:
                ok, message = await connector.test_connection()
                source.status = DataSourceStatus.CONNECTED if ok else DataSourceStatus.ERROR
                await db.commit()
                return ok, message
            finally:
                await connector.close()
        except Exception as e:
            source.status = DataSourceStatus.ERROR
            await db.commit()
            return False, f"Connection error: {str(e)}"

    @staticmethod
    async def list_sources(db: AsyncSession, org_id: uuid.UUID) -> List[DataSource]:
        stmt = (
            select(DataSource)
            .options(selectinload(DataSource.datasets))
            .where(DataSource.org_id == org_id)
            .order_by(DataSource.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_source(db: AsyncSession, org_id: uuid.UUID, source_id: uuid.UUID) -> DataSource:
        stmt = (
            select(DataSource)
            .options(selectinload(DataSource.datasets))
            .where(DataSource.id == source_id, DataSource.org_id == org_id)
        )
        res = await db.execute(stmt)
        source = res.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
        return source

    @staticmethod
    async def delete_source(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, source_id: uuid.UUID
    ) -> None:
        source = await DataSourceService.get_source(db, org_id, source_id)
        await db.delete(source)
        await db.commit()

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="datasource.delete",
            resource_type="data_source",
            resource_id=source_id,
        )
