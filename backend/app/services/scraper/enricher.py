import re
import httpx
import logging
from datetime import date, datetime
from typing import Optional
from bs4 import BeautifulSoup
from sqlalchemy import select, update
from app.database import async_session_factory
from app.models.company import Company
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)


class CompanyAgeEnricher:
    async def enrich_all(self, batch_size: int = 50) -> dict[str, int]:
        stats = {"checked": 0, "found_age": 0, "errors": 0}
        async with async_session_factory() as db:
            result = await db.execute(
                select(Company).where(
                    Company.founded_date.is_(None),
                    Company.is_active_hiring == True,
                ).limit(batch_size)
            )
            companies = result.scalars().all()
            stats["checked"] = len(companies)

            for company in companies:
                company_name = company.name
                try:
                    async with db.begin_nested():
                        age = await self._find_founded_date(company.name)
                        if age:
                            company.founded_date = age
                            company.founded_year = age.year
                            await db.flush()

                            await db.execute(
                                update(Opportunity)
                                .where(Opportunity.company == company.name)
                                .values(company_founded_date=age)
                            )
                            stats["found_age"] += 1
                except Exception as e:
                    logger.error(f"Error enriching {company_name}: {e}")
                    stats["errors"] += 1

            await db.commit()
        return stats

    async def _find_founded_date(self, company_name: str) -> Optional[date]:
        if not company_name:
            return None

        try:
            result = await self._check_crunchbase(company_name)
            if result:
                return result
        except Exception:
            pass

        return None

    async def _check_crunchbase(self, name: str) -> Optional[date]:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    "https://www.crunchbase.com/v4/data/autocompletes",
                    params={"query": name, "limit": 1},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Accept": "application/json",
                        "Referer": "https://www.crunchbase.com/",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    entities = data.get("entities", [])
                    if entities:
                        entity = entities[0]
                        props = entity.get("properties", entity)
                        founded = props.get("founded_on") or props.get("founded_date")
                        if founded:
                            try:
                                return date.fromisoformat(str(founded)[:10])
                            except (ValueError, TypeError):
                                try:
                                    return date(int(str(founded)[:4]), 1, 1)
                                except (ValueError, TypeError):
                                    pass
            except Exception:
                pass
        return None
