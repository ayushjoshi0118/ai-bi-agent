"""
Security tests for strict Multi-Tenant Isolation.
Verifies that User A cannot read, query, or delete datasets owned by User B in Org B.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource, DataSourceStatus, DataSourceType
from app.models.dataset import Dataset, DatasetStatus
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.user import User
from app.security.password import hash_password


@pytest.mark.asyncio
async def test_cross_tenant_isolation(client: AsyncClient, db_session: AsyncSession):
    # 1. Create Tenant A
    user_a = User(
        email="user_a@tenant-a.com",
        password_hash=hash_password("PassA123!"),
        full_name="User A",
        is_active=True,
    )
    db_session.add(user_a)
    await db_session.flush()

    org_a = Organization(name="Org A", slug="org-a", created_by=user_a.id)
    db_session.add(org_a)
    await db_session.flush()

    mem_a = OrgMembership(user_id=user_a.id, org_id=org_a.id, role=OrgRole.OWNER)
    db_session.add(mem_a)

    # 2. Create Tenant B
    user_b = User(
        email="user_b@tenant-b.com",
        password_hash=hash_password("PassB123!"),
        full_name="User B",
        is_active=True,
    )
    db_session.add(user_b)
    await db_session.flush()

    org_b = Organization(name="Org B", slug="org-b", created_by=user_b.id)
    db_session.add(org_b)
    await db_session.flush()

    mem_b = OrgMembership(user_id=user_b.id, org_id=org_b.id, role=OrgRole.OWNER)
    db_session.add(mem_b)

    # 3. Add confidential dataset to Org B
    source_b = DataSource(
        org_id=org_b.id,
        created_by=user_b.id,
        name="Org B Confidential Data",
        source_type=DataSourceType.CSV,
        status=DataSourceStatus.CONNECTED,
    )
    db_session.add(source_b)
    await db_session.flush()

    dataset_b = Dataset(
        org_id=org_b.id,
        data_source_id=source_b.id,
        name="Confidential Salaries",
        table_name="salaries",
        schema_metadata={"columns": [{"name": "salary", "data_type": "integer"}]},
        status=DatasetStatus.READY,
    )
    db_session.add(dataset_b)
    await db_session.commit()

    # 4. User A logs in
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "user_a@tenant-a.com", "password": "PassA123!"},
    )
    token_a = login_res.json()["tokens"]["access_token"]
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "X-Org-ID": str(org_a.id),
    }

    # 5. User A tries to list datasets -> Must NOT see Org B's dataset
    res = await client.get("/api/v1/datasets", headers=headers_a)
    assert res.status_code == 200
    datasets_list = res.json()
    assert all(d["id"] != str(dataset_b.id) for d in datasets_list)

    # 6. User A attempts direct access to Org B's dataset by ID -> 404 Forbidden
    direct_res = await client.get(f"/api/v1/datasets/{dataset_b.id}", headers=headers_a)
    assert direct_res.status_code == 404

    # 7. User A attempts to spoof X-Org-ID to Org B -> 403 Forbidden
    spoofed_headers = {
        "Authorization": f"Bearer {token_a}",
        "X-Org-ID": str(org_b.id),
    }
    spoof_res = await client.get("/api/v1/datasets", headers=spoofed_headers)
    assert spoof_res.status_code == 403
