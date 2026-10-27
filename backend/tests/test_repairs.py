import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import fakeredis
import fakeredis.aioredis
import pytest
from jose import jwt
from sqlalchemy import func, select

from app.auth.tokens import create_unsubscribe_token
from app.config import settings
from app.database import async_session_factory
from app.models.company import Company
from app.models.digest import DigestLog, DigestPreference
from app.models.profile import StudentProfile
from app.models.opportunity import Opportunity
from app.services.digests import scheduled_slot, send_due_digests
from app.services.ranking.engine import RankingEngine
from app.services.scraper.base import ScrapedOpportunity
from app.services.scraper.manager import ScraperManager


@pytest.mark.parametrize("password", ["x" * 73, "界" * 25])
async def test_long_passwords_return_validation_errors(client, password):
    for path, body in (("register", {"full_name": "Test"}), ("login", {})):
        response = await client.post(f"/api/auth/{path}", json={
            "email": "long@test.com", "password": password, **body,
        })
        assert response.status_code == 422


async def test_72_byte_password_still_works(client):
    body = {"email": "boundary@test.com", "password": "x" * 72, "full_name": "Boundary"}
    assert (await client.post("/api/auth/register", json=body)).status_code == 201
    assert (await client.post("/api/auth/login", json=body)).status_code == 200


async def test_unsubscribe_token_cannot_authenticate(client, registered_user):
    token = create_unsubscribe_token(uuid.UUID(registered_user["user"]["id"]))
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_malformed_signed_subject_is_unauthorized(client):
    token = jwt.encode({"sub": "not-a-uuid"}, settings.supabase_jwt_secret, algorithm="HS256")
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_regular_users_cannot_run_admin_jobs(client, auth_headers):
    for route in ("scrape", "enrich"):
        assert (await client.post(f"/api/admin/{route}", headers=auth_headers)).status_code == 403


async def admin_headers(client, monkeypatch):
    response = await client.post("/api/auth/register", json={
        "email": "admin@test.com", "password": "testpass", "full_name": "Admin",
    })
    monkeypatch.setattr(settings, "admin_user_ids", [response.json()["user"]["id"]])
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_admin_jobs_are_queued_and_broker_failure_is_visible(client, monkeypatch):
    headers = await admin_headers(client, monkeypatch)
    enqueue = Mock(return_value=("job-id", True))
    monkeypatch.setattr("app.routes.admin.enqueue_job", enqueue)
    response = await client.post("/api/admin/scrape", headers=headers)
    assert response.status_code == 202
    assert response.json()["task_id"] == "job-id"
    assert enqueue.call_args.args[1:] == ("scrape", "scraping")
    enqueue.side_effect = ConnectionError("offline")
    assert (await client.post("/api/admin/scrape", headers=headers)).status_code == 503


def test_job_locks_deduplicate_and_release(monkeypatch):
    from app.services import jobs
    server = fakeredis.FakeServer()
    monkeypatch.setattr(jobs, "redis_client", lambda: fakeredis.FakeRedis(server=server, decode_responses=True))
    task = Mock()
    task_id, created = jobs.enqueue_job(task, "scrape", "scraping")
    assert created
    assert jobs.enqueue_job(task, "scrape", "scraping") == (task_id, False)
    task.apply_async.assert_called_once()
    with jobs.job_lock("scrape", task_id) as acquired:
        assert acquired
        with jobs.job_lock("scrape", task_id) as duplicate:
            assert not duplicate
        with jobs.job_lock("scrape", "another-task") as overlap:
            assert not overlap
    assert jobs.enqueue_job(task, "scrape", "scraping")[1]


def test_failed_enqueue_releases_reservation(monkeypatch):
    from app.services import jobs
    server = fakeredis.FakeServer()
    monkeypatch.setattr(jobs, "redis_client", lambda: fakeredis.FakeRedis(server=server, decode_responses=True))
    task = Mock()
    task.apply_async.side_effect = ConnectionError("offline")
    with pytest.raises(ConnectionError):
        jobs.enqueue_job(task, "scrape", "scraping")
    task.apply_async.side_effect = None
    assert jobs.enqueue_job(task, "scrape", "scraping")[1]


@pytest.mark.parametrize("frequency,day,last,expected", [
    ("weekly", "sunday", None, True),
    ("weekly", "sunday", "2026-11-01T10:01:00+00:00", False),
    ("biweekly", "sunday", "2026-10-25T10:07:00+00:00", False),
    ("biweekly", "sunday", "2026-10-18T10:07:00+00:00", True),
    ("monthly", "sunday", "2026-10-04T10:07:00+00:00", True),
    ("weekly", "friday", None, False),
])
def test_digest_cadence_and_catchup(frequency, day, last, expected):
    pref = SimpleNamespace(frequency=frequency, day=day, time="10:00",
        last_sent_at=datetime.fromisoformat(last) if last else None)
    assert (scheduled_slot(pref, datetime(2026, 11, 1, 10, 17, tzinfo=timezone.utc)) is not None) == expected


def test_monthly_does_not_send_every_week():
    pref = SimpleNamespace(frequency="monthly", day="sunday", time="10:00", last_sent_at=None)
    assert scheduled_slot(pref, datetime(2026, 11, 8, 10, 5, tzinfo=timezone.utc)) is None


def test_digest_timezone(monkeypatch):
    monkeypatch.setattr(settings, "digest_timezone", "Asia/Kolkata")
    pref = SimpleNamespace(frequency="weekly", day="sunday", time="10:00", last_sent_at=None)
    now = datetime(2026, 11, 1, 4, 47, tzinfo=timezone.utc)
    assert scheduled_slot(pref, now) == datetime(2026, 11, 1, 4, 30, tzinfo=timezone.utc)


async def create_digest_preferences(registered_user, **overrides):
    user_id = uuid.UUID(registered_user["user"]["id"])
    async with async_session_factory() as db:
        db.add(StudentProfile(user_id=user_id, year="3rd Year", branch="CS", skills=["Python"],
            preferred_domains=["Engineering"], work_mode="remote"))
        pref = DigestPreference(**({"user_id": user_id, "frequency": "weekly", "day": "sunday",
            "time": "10:00", "enabled": True, "include_new_only": True,
            "min_match_score": 0.5, "max_results": 5} | overrides))
        db.add(pref)
        await db.commit()
        return pref.id


async def test_failed_digest_is_not_recorded_as_sent(registered_user, seed_opportunities):
    pref_id = await create_digest_preferences(registered_user)
    await seed_opportunities(2)
    email = SimpleNamespace(send_digest=AsyncMock(return_value=False))
    result = await send_due_digests(datetime(2026, 11, 1, 10, 7, tzinfo=timezone.utc), email_service=email)
    assert result["sent"] == 0 and result["failed"] == 1
    async with async_session_factory() as db:
        assert (await db.get(DigestPreference, pref_id)).last_sent_at is None
        assert (await db.execute(select(DigestLog))).scalar_one().error


async def test_successful_digest_is_not_resent(registered_user, seed_opportunities):
    await create_digest_preferences(registered_user)
    await seed_opportunities(2)
    email = SimpleNamespace(send_digest=AsyncMock(return_value=True))
    now = datetime(2026, 11, 1, 10, 7, tzinfo=timezone.utc)
    assert (await send_due_digests(now, email_service=email))["sent"] == 1
    assert (await send_due_digests(now + timedelta(minutes=1), email_service=email))["sent"] == 0
    email.send_digest.assert_awaited_once()


async def test_overlapping_digest_runs_send_once(registered_user, seed_opportunities):
    await create_digest_preferences(registered_user)
    await seed_opportunities(1)
    email = SimpleNamespace(send_digest=AsyncMock(return_value=True))
    now = datetime(2026, 11, 1, 10, 7, tzinfo=timezone.utc)
    results = await asyncio.gather(send_due_digests(now, email_service=email), send_due_digests(now, email_service=email))
    assert sum(result["sent"] for result in results) == 1
    email.send_digest.assert_awaited_once()


async def test_digest_new_only_and_result_limit(registered_user, seed_opportunities):
    last = datetime(2026, 10, 25, 10, 7, tzinfo=timezone.utc)
    await create_digest_preferences(registered_user, last_sent_at=last, max_results=1)
    await seed_opportunities(2, created_at=last - timedelta(days=1))
    await seed_opportunities(3, created_at=last + timedelta(days=1))
    email = SimpleNamespace(send_digest=AsyncMock(return_value=True))
    assert (await send_due_digests(datetime(2026, 11, 1, 10, 7, tzinfo=timezone.utc), email_service=email))["sent"] == 1
    assert len(email.send_digest.call_args.kwargs["opportunities"]) == 1


async def test_digest_score_filter(registered_user, seed_opportunities):
    await create_digest_preferences(registered_user, min_match_score=0.99)
    await seed_opportunities(1)
    email = SimpleNamespace(send_digest=AsyncMock(return_value=True))
    assert (await send_due_digests(datetime(2026, 11, 1, 10, 7, tzinfo=timezone.utc), email_service=email))["sent"] == 0
    email.send_digest.assert_not_called()


async def test_unsubscribe_confirmation_persists_and_is_idempotent(client, registered_user):
    pref_id = await create_digest_preferences(registered_user)
    token = create_unsubscribe_token(uuid.UUID(registered_user["user"]["id"]))
    assert (await client.get("/api/digest/unsubscribe", params={"token": token})).status_code == 200
    async with async_session_factory() as db:
        assert (await db.get(DigestPreference, pref_id)).enabled
    for _ in range(2):
        assert (await client.post("/api/digest/unsubscribe", json={"token": token})).status_code == 200
    async with async_session_factory() as db:
        assert not (await db.get(DigestPreference, pref_id)).enabled
    assert (await client.post("/api/digest/unsubscribe", json={"token": token + "tampered"})).status_code == 400
    assert (await client.post("/api/digest/unsubscribe", json={"token": registered_user["access_token"]})).status_code == 400


@pytest.mark.parametrize("payload", [{"time": "25:00"}, {"day": "wrong"}, {"max_results": 0}, {"min_match_score": 1.1}, {"enabled": None}])
async def test_invalid_digest_preferences_are_rejected(client, auth_headers, payload):
    assert (await client.put("/api/digest/preferences", headers=auth_headers, json=payload)).status_code == 422


async def test_match_pagination_includes_more_than_200_rows(client, auth_headers, seed_opportunities):
    await client.put("/api/profile", headers=auth_headers, json={
        "year": "3rd Year", "branch": "CS", "skills": ["Python"], "preferred_domains": ["Engineering"],
    })
    await seed_opportunities(235)
    pages = [(await client.get("/api/opportunities/match", headers=auth_headers,
        params={"page": page, "page_size": 20})).json() for page in (1, 2, 12)]
    assert pages[0]["total"] == 235 and pages[0]["total_pages"] == 12
    assert {item["id"] for item in pages[0]["items"]}.isdisjoint(item["id"] for item in pages[1]["items"])
    assert len(pages[2]["items"]) == 15


async def test_ranking_cache_changes_with_profile_and_limit(seed_opportunities):
    opportunities = await seed_opportunities(3)
    profile = StudentProfile(user_id=uuid.uuid4(), skills=["Python"], preferred_domains=[], work_mode="remote")
    engine = RankingEngine()
    engine._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        old_key = engine._cache_key(profile, opportunities, 1)
        assert len(await engine.rank_for_user(profile, opportunities, None, top_k=1)) == 1
        assert len(await engine.rank_for_user(profile, opportunities, None, top_k=3)) == 3
        profile.skills = ["Rust"]
        assert engine._cache_key(profile, opportunities, 1) != old_key
        assert engine._cache_key(profile, opportunities, 3) != engine._cache_key(profile, opportunities, 1)
    finally:
        await engine.aclose()


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
async def test_optional_provider_clients_initialize_without_network(provider, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setattr(settings, f"{provider}_api_key", "dummy-no-network")
    engine = RankingEngine()
    assert not engine._clients_initialized
    engine._init_clients()
    assert getattr(engine, f"{provider}_client") is not None
    await engine.aclose()


async def test_provider_failure_uses_fallback(seed_opportunities, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "dummy")
    monkeypatch.setattr(settings, "llm_provider", "openai")
    engine = RankingEngine()
    engine._llm_rank = AsyncMock(side_effect=RuntimeError("bad provider"))
    profile = StudentProfile(user_id=uuid.uuid4(), skills=["Python"], preferred_domains=[])
    assert len(await engine.rank_for_user(profile, await seed_opportunities(2), None, top_k=1)) == 1


def scraped(source_id, **values):
    return ScrapedOpportunity(**({"title": "Intern", "company": "Company", "description": "Python",
        "source": "fixture", "source_url": "https://example.com", "source_id": source_id} | values))


async def test_scraper_recovers_after_bad_record_and_duplicate():
    manager = ScraperManager()
    manager.scrapers = [SimpleNamespace(name="first", scrape=AsyncMock(return_value=[
        scraped("bad", title="x" * 301), scraped("good"), scraped("good"),
    ])), SimpleNamespace(name="second", scrape=AsyncMock(return_value=[scraped("next", company_slug="different")]))]
    assert await manager.run_all() == {"first": 1, "second": 1}
    async with async_session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(Opportunity))).scalar() == 2
        assert (await db.execute(select(func.count()).select_from(Company))).scalar() == 1


async def test_scraper_company_race_is_safe():
    async def run(source_id):
        manager = ScraperManager()
        manager.scrapers = [SimpleNamespace(name="fixture", scrape=AsyncMock(return_value=[scraped(source_id)]))]
        return await manager.run_all()
    results = await asyncio.gather(run("one"), run("two"))
    assert sum(result["fixture"] for result in results) == 2
    async with async_session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(Company))).scalar() == 1


async def test_readiness_and_frontend_origin(client, monkeypatch):
    monkeypatch.setattr(settings, "frontend_url", "https://opportunityradar-gamma.vercel.app")
    # Middleware is constructed at app creation; test its effective configured origins separately.
    assert "https://opportunityradar-gamma.vercel.app" in settings.allowed_origins
    assert (await client.get("/api/health")).status_code == 200
    assert (await client.get("/api/ready")).status_code == 200
    response = await client.options("/api/auth/login", headers={
        "Origin": "https://opportunityradar-gamma.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://opportunityradar-gamma.vercel.app"


async def test_readiness_recovers_after_bootstrap_failure(client, monkeypatch):
    import app.main as main
    real_initialize = main.initialize_schema
    monkeypatch.setattr(main, "initialize_schema", AsyncMock(side_effect=ConnectionError("offline")))
    async with main.lifespan(main.app):
        assert (await client.get("/api/health")).status_code == 200
        assert (await client.get("/api/ready")).status_code == 503
        monkeypatch.setattr(main, "initialize_schema", real_initialize)
        main.app.state.schema_ready = False
        assert (await client.get("/api/ready")).status_code == 200


async def test_enricher_recovers_after_record_database_error(monkeypatch):
    from datetime import date
    from app.services.scraper.enricher import CompanyAgeEnricher
    async with async_session_factory() as db:
        db.add_all([Company(name="First", is_active_hiring=True), Company(name="Second", is_active_hiring=True)])
        await db.commit()
    enricher = CompanyAgeEnricher()
    enricher._find_founded_date = AsyncMock(side_effect=[SimpleNamespace(year=2020), date(2020, 1, 1)])
    result = await enricher.enrich_all()
    assert result == {"checked": 2, "found_age": 1, "errors": 1}
    async with async_session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(Company).where(Company.founded_date.isnot(None)))).scalar() == 1
