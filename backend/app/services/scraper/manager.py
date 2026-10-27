import logging
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_factory
from app.models.opportunity import Opportunity
from app.models.company import Company
from app.config import settings
from app.services.scraper.wellfound import WellfoundScraper
from app.services.scraper.yc import YCombinatorScraper
from app.services.scraper.internshala import InternshalaScraper
from app.services.scraper.linkedin import LinkedInScraper

logger = logging.getLogger(__name__)


class ScraperManager:
    def __init__(self):
        self.scrapers = []
        if settings.scraper_internshala_enabled:
            self.scrapers.append(InternshalaScraper())
        if settings.scraper_linkedin_enabled:
            self.scrapers.append(LinkedInScraper())
        if settings.scraper_wellfound_enabled:
            self.scrapers.append(WellfoundScraper())
        self.scrapers.append(YCombinatorScraper())

    async def run_all(self) -> dict[str, int]:
        results = {}
        async with async_session_factory() as db:
            for scraper in self.scrapers:
                try:
                    opportunities = await scraper.scrape()
                    count = 0
                    for opp in opportunities:
                        try:
                            async with db.begin_nested():
                                exists = await self._opportunity_exists(db, opp.source, opp.source_id)
                                if exists:
                                    continue

                                company_id = await self._get_or_create_company(db, opp)

                                db.add(Opportunity(
                                    title=opp.title,
                                    company=opp.company,
                                    company_id=company_id,
                                    company_logo=opp.company_logo,
                                    company_founded_date=opp.company_founded_date,
                                    company_size=opp.company_size,
                                    company_funding_stage=opp.company_funding_stage,
                                    description=opp.description[:5000] if opp.description else "",
                                    source=opp.source,
                                    source_url=opp.source_url,
                                    source_id=opp.source_id,
                                    location=opp.location,
                                    work_mode=opp.work_mode or "remote",
                                    stipend=opp.stipend,
                                    stipend_min=opp.stipend_min,
                                    stipend_max=opp.stipend_max,
                                    duration=opp.duration,
                                    skills_required=opp.skills_required or [],
                                    domains=opp.domains or [],
                                    posted_date=opp.posted_date,
                                    deadline=opp.deadline,
                                    applicants_count=opp.applicants_count,
                                    is_active=True,
                                ))
                                await db.flush()
                            count += 1
                        except Exception as e:
                            logger.error(f"Error saving opportunity: {e}")
                            continue
                    await db.commit()
                    results[scraper.name] = count
                    logger.info(f"{scraper.name}: scraped {count} new opportunities")
                except Exception as e:
                    logger.error(f"{scraper.name} failed: {e}")
                    await db.rollback()
                    results[scraper.name] = 0
        return results

    async def _get_or_create_company(self, db: AsyncSession, opp) -> Optional[str]:
        if not opp.company:
            return None
        slug = opp.company_slug or opp.company.lower().replace(" ", "-").replace("'", "")
        result = await db.execute(insert(Company).values(
            name=opp.company, slug=slug, description=opp.company_description,
            logo_url=opp.company_logo, website=opp.company_website,
            founded_date=opp.company_founded_date,
            founded_year=opp.company_founded_date.year if opp.company_founded_date else None,
            company_size=opp.company_size, funding_stage=opp.company_funding_stage,
            source=opp.source, source_url=opp.source_url, is_active_hiring=True,
        ).on_conflict_do_nothing(index_elements=["name"]).returning(Company.id))
        company_id = result.scalar_one_or_none()
        if company_id is None:
            company_id = (await db.execute(select(Company.id).where(Company.name == opp.company))).scalar_one()
            if opp.company_founded_date:
                await db.execute(update(Company).where(
                    Company.id == company_id, Company.founded_date.is_(None)
                ).values(founded_date=opp.company_founded_date, founded_year=opp.company_founded_date.year))
        return company_id

    async def _opportunity_exists(self, db: AsyncSession, source: str, source_id: str) -> bool:
        if not source_id:
            return False
        result = await db.execute(
            select(Opportunity).where(
                Opportunity.source == source,
                Opportunity.source_id == source_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def deactivate_old(self, days: int = 60):
        async with async_session_factory() as db:
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            await db.execute(
                update(Opportunity)
                .where(Opportunity.created_at < cutoff)
                .values(is_active=False)
            )
            await db.commit()
