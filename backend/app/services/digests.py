import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from app.auth.tokens import create_unsubscribe_token
from app.config import settings
from app.database import async_session_factory
from app.models.digest import DigestLog, DigestPreference
from app.models.opportunity import Opportunity
from app.models.profile import StudentProfile
from app.models.user import User
from app.services.email.service import EmailService
from app.services.ranking.engine import RankingEngine

logger = logging.getLogger(__name__)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def scheduled_slot(pref, now):
    """Return an unsent due slot, allowing a day's catch-up after worker downtime.

    Monthly means the first chosen weekday of each calendar month. Biweekly
    is anchored to the previous successful send. All preferences use DIGEST_TIMEZONE.
    """
    local = now.astimezone(ZoneInfo(settings.digest_timezone))
    try:
        weekday = WEEKDAYS.index(pref.day.lower())
        hour, minute = map(int, pref.time.split(":"))
        slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if pref.frequency == "monthly":
            slot = slot.replace(day=1)
            slot += timedelta(days=(weekday - slot.weekday()) % 7)
            if slot > local:
                slot = slot.replace(day=1) - relativedelta(months=1)
                slot += timedelta(days=(weekday - slot.weekday()) % 7)
        else:
            slot -= timedelta(days=(slot.weekday() - weekday) % 7)
            if slot > local:
                slot -= timedelta(days=7)
    except (ValueError, TypeError, AttributeError):
        return None
    slot = slot.astimezone(timezone.utc)
    if not timedelta(0) <= now - slot < timedelta(days=1):
        return None
    if pref.last_sent_at:
        last = pref.last_sent_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last >= slot:
            return None
        if pref.frequency == "biweekly" and slot - last < timedelta(days=13):
            return None
    return slot


async def send_due_digests(now=None, email_service=None, ranking_engine=None):
    now = now or datetime.now(timezone.utc)
    email_service = email_service or EmailService()
    own_engine = ranking_engine is None
    ranking_engine = ranking_engine or RankingEngine()
    sent = failed = 0
    try:
        async with async_session_factory() as db:
            ids = list((await db.execute(select(DigestPreference.id).where(
                DigestPreference.enabled.is_(True)))).scalars())
        for pref_id in ids:
            try:
                async with async_session_factory() as db:
                    pref = (await db.execute(select(DigestPreference).where(
                        DigestPreference.id == pref_id,
                        DigestPreference.enabled.is_(True),
                    ).with_for_update(skip_locked=True))).scalar_one_or_none()
                    if not pref or scheduled_slot(pref, now) is None:
                        continue
                    user = await db.get(User, pref.user_id)
                    profile = (await db.execute(select(StudentProfile).where(
                        StudentProfile.user_id == pref.user_id))).scalar_one_or_none()
                    if not user or not user.is_active or not profile:
                        continue
                    query = select(Opportunity).where(Opportunity.is_active.is_(True))
                    if pref.include_new_only and pref.last_sent_at:
                        query = query.where(Opportunity.created_at > pref.last_sent_at)
                    opportunities = list((await db.execute(query.order_by(Opportunity.id))).scalars())
                    rankings = await ranking_engine.rank_for_user(profile, opportunities, db, top_k=None)
                    by_id = {str(opp.id): opp for opp in opportunities}
                    matches = []
                    for ranking in rankings:
                        opp = by_id.get(ranking["opportunity_id"])
                        if not opp or ranking["score"] < pref.min_match_score * 100:
                            continue
                        matches.append({field: getattr(opp, field) for field in (
                            "title", "company", "location", "stipend", "work_mode", "source_url", "skills_required"
                        )} | {"score": ranking["score"], "reason": ranking["reason"]})
                        if len(matches) >= pref.max_results:
                            break
                    if not matches:
                        continue
                    success = await email_service.send_digest(
                        to_email=user.email, to_name=user.full_name,
                        opportunities=matches, profile_name=user.full_name.split()[0],
                        unsubscribe_token=create_unsubscribe_token(user.id),
                    )
                    db.add(DigestLog(user_id=user.id, sent_at=now,
                        opportunities_count=len(matches),
                        error=None if success else "Email delivery failed"))
                    if success:
                        pref.last_sent_at = now
                        sent += 1
                    else:
                        failed += 1
                    await db.commit()
            except Exception:
                logger.exception("Failed to process digest preference %s", pref_id)
                failed += 1
        return {"sent": sent, "failed": failed, "total_prefs": len(ids)}
    finally:
        if own_engine:
            await ranking_engine.aclose()
