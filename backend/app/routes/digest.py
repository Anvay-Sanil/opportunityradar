import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal
from app.auth.tokens import unsubscribe_user_id
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.digest import DigestPreference, DigestLog
from app.auth.deps import get_current_user

router = APIRouter(prefix="/api/digest", tags=["digest"])


class DigestPreferenceResponse(BaseModel):
    id: str
    enabled: bool
    frequency: str
    day: str
    time: str
    max_results: int
    min_match_score: float
    include_new_only: bool
    last_sent_at: Optional[str] = None
    timezone: str = "UTC"

    class Config:
        from_attributes = True


class DigestPreferenceUpdate(BaseModel):
    enabled: Optional[bool] = None
    frequency: Optional[Literal["weekly", "biweekly", "monthly"]] = None
    day: Optional[Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]] = None
    time: Optional[str] = None
    max_results: Optional[int] = Field(default=None, ge=1, le=20)
    min_match_score: Optional[float] = Field(default=None, ge=0, le=1)
    include_new_only: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_values(cls, values):
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Digest preferences cannot be null")
        return values

    @field_validator("time")
    @classmethod
    def validate_time(cls, value):
        from datetime import time
        try:
            if len(value) != 5:
                raise ValueError()
            time.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError("Time must be HH:MM in 24-hour format")
        return value


class DigestLogResponse(BaseModel):
    id: str
    sent_at: str
    opportunities_count: int
    opened: bool
    opened_at: Optional[str] = None
    error: Optional[str] = None


@router.get("/preferences", response_model=DigestPreferenceResponse)
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigestPreference).where(DigestPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = DigestPreference(user_id=user.id)
        db.add(pref)
        await db.flush()

    return DigestPreferenceResponse(
        id=str(pref.id),
        enabled=pref.enabled,
        frequency=pref.frequency,
        day=pref.day,
        time=pref.time,
        max_results=pref.max_results,
        min_match_score=pref.min_match_score,
        include_new_only=pref.include_new_only,
        last_sent_at=pref.last_sent_at.isoformat() if pref.last_sent_at else None,
        timezone=settings.digest_timezone,
    )


@router.put("/preferences", response_model=DigestPreferenceResponse)
async def update_preferences(
    req: DigestPreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigestPreference).where(DigestPreference.user_id == user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = DigestPreference(user_id=user.id)
        db.add(pref)

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pref, key, value)

    await db.flush()
    return DigestPreferenceResponse(
        id=str(pref.id),
        enabled=pref.enabled,
        frequency=pref.frequency,
        day=pref.day,
        time=pref.time,
        max_results=pref.max_results,
        min_match_score=pref.min_match_score,
        include_new_only=pref.include_new_only,
        last_sent_at=pref.last_sent_at.isoformat() if pref.last_sent_at else None,
        timezone=settings.digest_timezone,
    )


@router.get("/logs", response_model=list[DigestLogResponse])
async def get_digest_logs(
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DigestLog)
        .where(DigestLog.user_id == user.id)
        .order_by(DigestLog.sent_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [DigestLogResponse(
        id=str(log.id),
        sent_at=log.sent_at.isoformat() if log.sent_at else "",
        opportunities_count=log.opportunities_count,
        opened=log.opened,
        opened_at=log.opened_at.isoformat() if log.opened_at else None,
        error=log.error,
    ) for log in logs]


@router.get("/unsubscribe")
async def unsubscribe(token: str = Query(...)):
    unsubscribe_user_id(token)
    return {"message": "Confirm below to stop receiving digests."}


class UnsubscribeRequest(BaseModel):
    token: str


@router.post("/unsubscribe")
async def confirm_unsubscribe(req: UnsubscribeRequest, db: AsyncSession = Depends(get_db)):
    user_id = unsubscribe_user_id(req.token)
    pref = (await db.execute(select(DigestPreference).where(
        DigestPreference.user_id == user_id).with_for_update())).scalar_one_or_none()
    if pref:
        pref.enabled = False
        await db.flush()
    return {"message": "You have been unsubscribed from digests."}
