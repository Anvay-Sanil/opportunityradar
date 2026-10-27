import os
import uuid

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.engine import make_url

# Never inherit the application's real DATABASE_URL or API credentials.
test_url = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:review-test-only@127.0.0.1:15432/opportunityradar_test")
if not (make_url(test_url).database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must refer to a disposable database ending in _test")
os.environ.update(DATABASE_URL=test_url, SUPABASE_JWT_SECRET="test-only-signing-secret",
    REDIS_URL="", OPENAI_API_KEY="", ANTHROPIC_API_KEY="", GEMINI_API_KEY="",
    ADMIN_USER_IDS='[]', DIGEST_TIMEZONE="UTC", FRONTEND_URL="https://opportunityradar-gamma.vercel.app")

from app.main import app
from app.database import engine, async_session_factory
from app.models.base import Base
from app.models.opportunity import Opportunity

TEST_EMAIL = "testuser@test.com"
TEST_PASSWORD = "testpass123"


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        tables = ", ".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def registered_user(client):
    response = await client.post("/api/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": "Test User",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest_asyncio.fixture
async def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['access_token']}"}


@pytest_asyncio.fixture
async def seed_opportunities():
    async def seed(count, **overrides):
        async with async_session_factory() as db:
            opportunities = [Opportunity(**({
                "title": f"Python internship {index}", "company": "Example",
                "description": "Build Python applications", "source": "test",
                "source_id": str(uuid.uuid4()), "source_url": "https://example.com/job",
                "skills_required": ["Python"], "domains": ["Engineering"],
                "work_mode": "remote", "location": "Remote",
            } | overrides)) for index in range(count)]
            db.add_all(opportunities)
            await db.commit()
            return opportunities
    return seed
