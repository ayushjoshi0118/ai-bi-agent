"""
Pytest configuration and shared test fixtures with in-memory SQLite database.
"""

import asyncio
import os
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import get_async_session
from app.dependencies import get_db
from app.main import app
from app.models.base import Base
from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.user import User
from app.security.password import hash_password

# Use in-memory SQLite for rapid, isolated, local unit & integration testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def init_test_db():
    """Initialize test database tables before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="analyst@example.com",
        password_hash=hash_password("SecurePassword123!"),
        full_name="Jane Analyst",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_org(db_session: AsyncSession, test_user: User) -> Organization:
    org = Organization(
        name="Acme Corp",
        slug="acme-corp",
        created_by=test_user.id,
    )
    db_session.add(org)
    await db_session.flush()

    membership = OrgMembership(
        user_id=test_user.id,
        org_id=org.id,
        role=OrgRole.OWNER,
    )
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(org)
    return org
