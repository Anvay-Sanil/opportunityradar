"""A bounded, traffic-driven catalog refresh for the free web service."""
import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import async_session_factory
from app.models.company import Company
from app.models.feed import FeedRefresh
from app.models.opportunity import Opportunity
from app.services.scraper.greenhouse import GreenhouseFeed

logger = logging.getLogger(__name__)
_task = None
LOCK_ID = 417802941
INITIAL_LOAD_TIMEOUT = 10


async def save_snapshot(db, snapshot):
    ids = []
    for item in snapshot.opportunities:
        company_insert = insert(Company).values(name=item.company, slug=item.company.lower().replace(" ", "-"))
        await db.execute(company_insert.on_conflict_do_nothing(index_elements=["name"]))
        company_id = (await db.execute(select(Company.id).where(Company.name == item.company))).scalar_one()
        values = {key: getattr(item, key) for key in ("title", "company", "description", "source", "source_id",
            "source_url", "location", "work_mode", "skills_required", "domains", "posted_date")}
        values.update(company_id=company_id, is_active=True)
        statement = insert(Opportunity).values(**values)
        await db.execute(statement.on_conflict_do_update(constraint="uq_opportunity_source",
            set_={key: getattr(statement.excluded, key) for key in values if key not in {"source", "source_id"}}
            | {"updated_at": datetime.now(timezone.utc)}))
        ids.append(item.source_id)
    if snapshot.complete:
        await db.execute(update(Opportunity).where(Opportunity.source == "greenhouse",
            Opportunity.source_id.startswith(snapshot.board + ":"), Opportunity.source_id.not_in(ids)
        ).values(is_active=False))


async def refresh_if_due():
    if not settings.public_feed_enabled:
        return
    async with async_session_factory() as db:
        async with db.begin():
            # Transaction lock also protects against duplicate refreshes across processes.
            if not (await db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_ID})).scalar():
                return
            now = datetime.now(timezone.utc)
            state = await db.get(FeedRefresh, "greenhouse")
            if state and state.next_attempt_at > now:
                return
            if state is None:
                state = FeedRefresh(name="greenhouse", next_attempt_at=now)
                db.add(state)
            try:
                snapshots = await asyncio.wait_for(GreenhouseFeed().fetch(), timeout=25)
            except Exception:
                logger.exception("Public employer feed refresh failed")
                snapshots = []
            for snapshot in snapshots:
                await save_snapshot(db, snapshot)
            from app.services.scraper.greenhouse import BOARDS
            complete = len(snapshots) == len(BOARDS) and all(snapshot.complete for snapshot in snapshots)
            state.last_error = None if complete else "Some employer feeds could not be refreshed"
            state.next_attempt_at = now + (timedelta(hours=6) if complete else timedelta(minutes=15))
            if snapshots:
                state.last_success_at = now
            logger.info("Public internship refresh: %s postings from %s employers; complete=%s",
                sum(len(snapshot.opportunities) for snapshot in snapshots), len(snapshots), complete)


def _observe_result(task):
    if not task.cancelled() and task.exception():
        logger.error("Catalog refresh failed", exc_info=task.exception())


def start_refresh():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(refresh_if_due())
        _task.add_done_callback(_observe_result)
    return _task


async def stop_refresh():
    if _task is not None and not _task.done():
        _task.cancel()
        with suppress(asyncio.CancelledError):
            await _task


async def prepare_catalog(db) -> int:
    total = (await db.execute(select(func.count()).select_from(Opportunity).where(Opportunity.is_active == True))).scalar_one()
    if not settings.public_feed_enabled:
        return total
    task = start_refresh()
    if total:
        return total  # Serve the existing catalog while a due refresh runs.
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=INITIAL_LOAD_TIMEOUT)
    except Exception:
        raise HTTPException(status_code=503, detail="Internships are being refreshed. Please try again shortly.")
    total = (await db.execute(select(func.count()).select_from(Opportunity).where(Opportunity.is_active == True))).scalar_one()
    state = await db.get(FeedRefresh, "greenhouse")
    if not total and (state is None or state.last_error):
        raise HTTPException(status_code=503, detail="Employer feeds are temporarily unavailable. Please try again shortly.")
    return total
