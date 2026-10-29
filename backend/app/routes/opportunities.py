import uuid
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from dateutil.relativedelta import relativedelta
from app.database import get_db
from app.models.opportunity import Opportunity
from app.models.profile import StudentProfile
from app.models.user import User
from app.auth.deps import get_current_user
from app.services.ranking.engine import RankingEngine
from app.services.public_feed import prepare_catalog

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

ranking_engine = RankingEngine()

ALLOWED_SORT_FIELDS = {"created_at", "posted_date", "stipend_min"}


class OpportunityResponse(BaseModel):
    id: str
    title: str
    company: str
    company_logo: Optional[str] = None
    company_founded_date: Optional[str] = None
    company_size: Optional[str] = None
    company_funding_stage: Optional[str] = None
    description: str
    source: str
    source_url: str
    location: Optional[str] = None
    work_mode: Optional[str] = None
    stipend: Optional[str] = None
    stipend_min: Optional[int] = None
    stipend_max: Optional[int] = None
    duration: Optional[str] = None
    skills_required: list[str] = []
    domains: list[str] = []
    posted_date: Optional[str] = None
    deadline: Optional[str] = None
    applicants_count: Optional[int] = None
    is_active: bool = True
    match_score: float = 0.0
    match_reason: Optional[str] = None
    skill_gaps: list[str] = []
    created_at: Optional[str] = None
    company_age_months: Optional[float] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: list[OpportunityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    catalog_total: int = 0


def build_response(o: Opportunity, today: Optional[date] = None) -> dict:
    if today is None:
        today = date.today()
    return {
        "id": str(o.id),
        "title": o.title,
        "company": o.company,
        "company_logo": o.company_logo,
        "company_founded_date": o.company_founded_date.isoformat() if o.company_founded_date else None,
        "company_size": o.company_size,
        "company_funding_stage": o.company_funding_stage,
        "description": o.description or "",
        "source": o.source,
        "source_url": o.source_url or "",
        "location": o.location,
        "work_mode": o.work_mode,
        "stipend": o.stipend,
        "stipend_min": o.stipend_min,
        "stipend_max": o.stipend_max,
        "duration": o.duration,
        "skills_required": o.skills_required or [],
        "domains": o.domains or [],
        "posted_date": o.posted_date.isoformat() if o.posted_date else None,
        "deadline": o.deadline.isoformat() if o.deadline else None,
        "applicants_count": o.applicants_count,
        "is_active": o.is_active,
        "match_score": getattr(o, "match_score", 0.0),
        "match_reason": getattr(o, "match_reason", None),
        "skill_gaps": getattr(o, "skill_gaps", []),
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "company_age_months": round((today - o.company_founded_date).days / 30.44, 1) if o.company_founded_date else None,
    }


@router.get("", response_model=PaginatedResponse)
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    stipend_min: Optional[int] = Query(None),
    founded_within_months: Optional[int] = Query(None, description="Only companies founded within N months"),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    catalog_total = await prepare_catalog(db)
    query = select(Opportunity).where(Opportunity.is_active == True)

    if search:
        search_filter = or_(
            Opportunity.title.ilike(f"%{search}%"),
            Opportunity.company.ilike(f"%{search}%"),
            Opportunity.description.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
    if source:
        query = query.where(Opportunity.source == source)
    if domain:
        query = query.where(Opportunity.domains.any(domain))
    if location:
        query = query.where(Opportunity.location.ilike(f"%{location}%"))
    if work_mode:
        query = query.where(Opportunity.work_mode == work_mode)
    if stipend_min:
        query = query.where(
            or_(
                Opportunity.stipend_min >= stipend_min,
                Opportunity.stipend_max >= stipend_min,
            )
        )
    if founded_within_months:
        cutoff = date.today() - relativedelta(months=founded_within_months)
        query = query.where(
            and_(
                Opportunity.company_founded_date.isnot(None),
                Opportunity.company_founded_date >= cutoff,
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "created_at"
    sort_column = getattr(Opportunity, sort_by)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    opportunities = result.scalars().all()

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile and opportunities:
        scored = await ranking_engine.rank_for_user(profile, list(opportunities), db, top_k=len(opportunities))
        score_map = {s["opportunity_id"]: s for s in scored}
        for opp in opportunities:
            s = score_map.get(str(opp.id))
            if s:
                opp.match_score = s.get("score", 0) / 100.0
                opp.match_reason = s.get("reason", "")
                opp.skill_gaps = s.get("skill_gaps", [])

    today = date.today()
    return PaginatedResponse(
        catalog_total=catalog_total,
        items=[OpportunityResponse(**build_response(o, today)) for o in opportunities],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 1,
    )


@router.get("/match", response_model=PaginatedResponse)
async def get_matches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    founded_within_months: Optional[int] = Query(None, description="Only companies founded within N months"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Complete your profile first to get matches")

    catalog_total = await prepare_catalog(db)
    query = select(Opportunity).where(Opportunity.is_active == True)
    if founded_within_months:
        cutoff = date.today() - relativedelta(months=founded_within_months)
        query = query.where(
            and_(
                Opportunity.company_founded_date.isnot(None),
                Opportunity.company_founded_date >= cutoff,
            )
        )

    if profile.preferred_locations:
        location_filter = or_(*[Opportunity.location.ilike(f"%{loc}%") for loc in profile.preferred_locations])
        query = query.where(location_filter)

    result = await db.execute(query.order_by(Opportunity.created_at.desc(), Opportunity.id))
    all_opps = list(result.scalars())
    scored = await ranking_engine.rank_for_user(profile, all_opps, db, top_k=None)
    total = len(scored)
    selected = scored[(page - 1) * page_size:page * page_size]
    by_id = {str(opp.id): opp for opp in all_opps}
    opportunities = []
    for ranking in selected:
        opp = by_id[ranking["opportunity_id"]]
        opp.match_score = ranking["score"] / 100.0
        opp.match_reason = ranking["reason"]
        opp.skill_gaps = ranking["skill_gaps"]
        opportunities.append(opp)

    today = date.today()
    return PaginatedResponse(
        catalog_total=catalog_total,
        items=[OpportunityResponse(**build_response(o, today)) for o in opportunities],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    )
    opp = result.scalar_one_or_none()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return OpportunityResponse(**build_response(opp))
