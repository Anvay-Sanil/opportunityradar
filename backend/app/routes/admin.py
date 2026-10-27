import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_admin_user
from app.models.user import User
from app.services.jobs import enqueue_job

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


class JobResponse(BaseModel):
    task_id: str
    message: str


async def submit(task, name, queue):
    try:
        task_id, created = await asyncio.to_thread(enqueue_job, task, name, queue)
    except Exception:
        logger.exception("Could not queue %s", name)
        raise HTTPException(status_code=503, detail="Background jobs are unavailable. Please try again later.")
    if not task_id:
        raise HTTPException(status_code=409, detail="A job is already being scheduled. Please try again.")
    return JobResponse(task_id=task_id, message="Job queued" if created else "Job is already queued or running")


@router.post("/scrape", response_model=JobResponse, status_code=202)
async def trigger_scrape(user: User = Depends(get_admin_user)):
    from app.celery_app import scrape_all_opportunities
    return await submit(scrape_all_opportunities, "scrape", "scraping")


@router.post("/enrich", response_model=JobResponse, status_code=202)
async def enrich_companies(user: User = Depends(get_admin_user)):
    from app.celery_app import enrich_company_ages
    return await submit(enrich_company_ages, "enrich", "scraping")
