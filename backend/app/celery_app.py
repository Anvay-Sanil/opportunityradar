import asyncio

from celery import Celery
from app.config import settings
from app.services.jobs import job_lock

celery_app = Celery("opportunityradar", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    timezone="UTC", enable_utc=True, task_track_started=True,
    task_soft_time_limit=840, task_time_limit=900,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2, broker_connection_max_retries=3,
    result_expires=86400,
    beat_schedule={
        "scrape-all-sources": {
            "task": "app.celery_app.scrape_all_opportunities",
            "schedule": settings.scraper_interval_hours * 3600,
            "options": {"queue": "scraping", "expires": 1200},
        },
        "send-due-digests": {
            "task": "app.celery_app.send_digests", "schedule": 60,
            "options": {"queue": "email", "expires": 60},
        },
        "deactivate-old-opportunities": {
            "task": "app.celery_app.deactivate_old_opportunities", "schedule": 86400,
            "options": {"queue": "maintenance"},
        },
    },
)


def run_job(name, task_id, make_coroutine):
    with job_lock(name, task_id) as acquired:
        if not acquired:
            return {"status": "already_running"}
        return asyncio.run(make_coroutine())


@celery_app.task(bind=True)
def scrape_all_opportunities(self):
    from app.services.scraper.manager import ScraperManager
    return run_job("scrape", self.request.id, lambda: ScraperManager().run_all())


@celery_app.task(bind=True)
def enrich_company_ages(self):
    from app.services.scraper.enricher import CompanyAgeEnricher
    return run_job("enrich", self.request.id, lambda: CompanyAgeEnricher().enrich_all(batch_size=30))


@celery_app.task(bind=True)
def send_digests(self):
    from app.services.digests import send_due_digests
    return run_job("digests", self.request.id, send_due_digests)


@celery_app.task(bind=True)
def deactivate_old_opportunities(self):
    from app.services.scraper.manager import ScraperManager
    return run_job("maintenance", self.request.id, lambda: ScraperManager().deactivate_old(days=60))
