import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.feed import FeedRefresh
from app.models.opportunity import Opportunity
from app.services import public_feed
from app.services.scraper import greenhouse
from app.services.scraper.greenhouse import BoardSnapshot, GreenhouseFeed


def job(job_id=1, **changes):
    return {"id": job_id, "title": "Software Engineer Intern", "absolute_url": f"https://example.com/jobs/{job_id}",
        "location": {"name": "Bengaluru, India"}, "content": "&lt;p&gt;Build Python and SQL applications&lt;/p&gt;",
        "first_published": "2026-10-20T10:00:00Z", **changes}


def snapshot(board="stripe", job_id=1, **changes):
    return BoardSnapshot(board, [GreenhouseFeed().parse_job(board, board.title(), job(job_id, **changes))])


def test_parse_public_posting_without_inventing_company_age_or_pay():
    item = GreenhouseFeed().parse_job("stripe", "Stripe", job())
    assert item.source_id == "stripe:1" and item.source == "greenhouse"
    assert item.description == "Build Python and SQL applications"
    assert item.location == "Bengaluru, India" and item.work_mode == "onsite"
    assert item.skills_required == ["Python", "SQL"]
    assert item.posted_date.isoformat() == "2026-10-20"
    assert item.company_founded_date is None and item.stipend is None
    assert GreenhouseFeed().parse_job("stripe", "Stripe", job(title="Senior Engineer")) is None
    assert GreenhouseFeed().parse_job("stripe", "Stripe", job(absolute_url="javascript:alert(1)")) is None


async def test_failed_detail_does_not_make_board_look_complete(monkeypatch):
    monkeypatch.setattr(greenhouse, "BOARDS", {"stripe": "Stripe"})
    async def get_json(client, path):
        if path.endswith("/jobs"):
            return {"jobs": [job(1), job(2)], "meta": {"total": 2}}
        if path.endswith("/2"):
            raise httpx.ReadTimeout("unavailable")
        return job(1)
    feed = GreenhouseFeed()
    monkeypatch.setattr(feed, "_get_json", get_json)
    result = await feed.fetch()
    assert len(result) == 1 and len(result[0].opportunities) == 1
    assert not result[0].complete


async def test_reject_oversized_public_feed():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * (greenhouse.MAX_RESPONSE_BYTES + 1)))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="response limit"):
            await GreenhouseFeed()._get_json(client, "stripe/jobs")


async def test_feed_upsert_preserves_ids_and_only_retires_successful_board():
    async with async_session_factory() as db:
        await public_feed.save_snapshot(db, snapshot())
        await public_feed.save_snapshot(db, snapshot("figma", 2))
        await db.commit()
        first_id = (await db.execute(select(Opportunity.id).where(Opportunity.source_id == "stripe:1"))).scalar_one()
        await public_feed.save_snapshot(db, snapshot(title="Data Science Intern"))
        await db.commit()
        saved = (await db.execute(select(Opportunity).where(Opportunity.source_id == "stripe:1"))).scalar_one()
        await db.refresh(saved)
        assert saved.id == first_id and saved.title == "Data Science Intern"
        await public_feed.save_snapshot(db, BoardSnapshot("stripe", [], complete=False))
        await db.commit()
        await db.refresh(saved)
        assert saved.is_active
        await public_feed.save_snapshot(db, BoardSnapshot("stripe", []))
        await db.commit()
        await db.refresh(saved)
        assert not saved.is_active
        other = (await db.execute(select(Opportunity).where(Opportunity.source_id == "figma:2"))).scalar_one()
        assert other.is_active


async def test_concurrent_refreshes_and_restart_respect_durable_cooldown(monkeypatch):
    monkeypatch.setattr(settings, "public_feed_enabled", True)
    monkeypatch.setattr(greenhouse, "BOARDS", {"stripe": "Stripe"})
    async def fetch():
        await asyncio.sleep(0.05)
        return [snapshot()]
    fetch_mock = AsyncMock(side_effect=fetch)
    monkeypatch.setattr(GreenhouseFeed, "fetch", fetch_mock)
    await asyncio.gather(public_feed.refresh_if_due(), public_feed.refresh_if_due())
    await public_feed.refresh_if_due()
    assert fetch_mock.await_count == 1
    async with async_session_factory() as db:
        state = await db.get(FeedRefresh, "greenhouse")
        assert state.last_error is None and state.last_success_at is not None
        assert state.next_attempt_at > datetime.now(timezone.utc) + timedelta(hours=5)


async def test_failed_board_keeps_existing_records_and_sets_retry(monkeypatch):
    monkeypatch.setattr(settings, "public_feed_enabled", True)
    monkeypatch.setattr(GreenhouseFeed, "fetch", AsyncMock(return_value=[]))
    async with async_session_factory() as db:
        await public_feed.save_snapshot(db, snapshot())
        await db.commit()
    await public_feed.refresh_if_due()
    async with async_session_factory() as db:
        assert (await db.execute(select(Opportunity))).scalar_one().is_active
        state = await db.get(FeedRefresh, "greenhouse")
        assert state.last_error and state.last_success_at is None
        assert state.next_attempt_at < datetime.now(timezone.utc) + timedelta(minutes=16)


async def test_empty_feed_failure_is_a_retryable_error_not_empty_success(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "public_feed_enabled", True)
    monkeypatch.setattr(GreenhouseFeed, "fetch", AsyncMock(return_value=[]))
    response = await client.get("/api/opportunities", headers=auth_headers)
    assert response.status_code == 503
    assert "Employer feeds" in response.json()["detail"]


async def test_first_catalog_request_imports_real_feed_and_reports_unfiltered_count(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "public_feed_enabled", True)
    monkeypatch.setattr(greenhouse, "BOARDS", {"stripe": "Stripe"})
    monkeypatch.setattr(GreenhouseFeed, "fetch", AsyncMock(return_value=[snapshot()]))
    response = await client.get("/api/opportunities", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == response.json()["catalog_total"] == 1
    assert response.json()["items"][0]["source_url"] == "https://example.com/jobs/1"
    response = await client.get("/api/opportunities?search=doesnotexist", headers=auth_headers)
    assert response.json()["total"] == 0 and response.json()["catalog_total"] == 1
    await public_feed.stop_refresh()


async def test_slow_initial_import_finishes_after_retryable_response(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "public_feed_enabled", True)
    monkeypatch.setattr(greenhouse, "BOARDS", {"stripe": "Stripe"})
    monkeypatch.setattr(public_feed, "INITIAL_LOAD_TIMEOUT", 0.01)
    async def fetch():
        await asyncio.sleep(0.05)
        return [snapshot()]
    monkeypatch.setattr(GreenhouseFeed, "fetch", AsyncMock(side_effect=fetch))
    response = await client.get("/api/opportunities", headers=auth_headers)
    assert response.status_code == 503 and "being refreshed" in response.json()["detail"]
    await public_feed._task
    response = await client.get("/api/opportunities", headers=auth_headers)
    assert response.status_code == 200 and response.json()["total"] == 1
    await public_feed.stop_refresh()
