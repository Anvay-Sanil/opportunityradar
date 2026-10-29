"""Read published employer postings from Greenhouse's public Job Board API."""
import asyncio
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.scraper.base import ScrapedOpportunity

logger = logging.getLogger(__name__)
BOARDS = {
    "stripe": "Stripe", "figma": "Figma", "databricks": "Databricks",
    "cloudflare": "Cloudflare", "mongodb": "MongoDB",
}
INTERNSHIP = re.compile(r"\b(?:intern(?:ship)?s?|co-?op|apprentice(?:ship)?|trainee)\b", re.I)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass
class BoardSnapshot:
    board: str
    opportunities: list[ScrapedOpportunity]
    # If a detail request failed, do not retire any old postings from that board.
    complete: bool = True


class GreenhouseFeed:
    async def _get_json(self, client, path):
        async with client.stream("GET", f"https://boards-api.greenhouse.io/v1/boards/{path}") as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("Employer feed exceeded response limit")
            return json.loads(body)

    async def fetch(self) -> list[BoardSnapshot]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8), follow_redirects=False,
                headers={"User-Agent": "OpportunityRadar/1.0 (public internship feed)", "Accept": "application/json"}) as client:
            limiter = asyncio.Semaphore(4)

            async def board_snapshot(board, company):
                try:
                    async with limiter:
                        payload = await self._get_json(client, f"{board}/jobs")
                    jobs = payload["jobs"]
                    if not isinstance(jobs, list) or payload.get("meta", {}).get("total", len(jobs)) != len(jobs):
                        raise ValueError("Incomplete employer job list")
                    candidates = [job for job in jobs if INTERNSHIP.search(job.get("title", ""))]
                    complete = len(candidates) <= 100

                    async def detail(job):
                        nonlocal complete
                        try:
                            async with limiter:
                                data = await self._get_json(client, f"{board}/jobs/{int(job['id'])}")
                            item = self.parse_job(board, company, data)
                            if item is None:
                                complete = False
                            return item
                        except Exception:
                            complete = False
                            logger.warning("Could not read an internship detail from board %s", board)
                            return None

                    parsed = await asyncio.gather(*(detail(job) for job in candidates[:100]))
                    return BoardSnapshot(board, [item for item in parsed if item], complete)
                except Exception:
                    logger.warning("Employer feed unavailable: %s", board)
                    return None

            snapshots = await asyncio.gather(*(board_snapshot(board, company) for board, company in BOARDS.items()))
        return [snapshot for snapshot in snapshots if snapshot is not None]

    def parse_job(self, board, company, data) -> ScrapedOpportunity | None:
        title = html.unescape(data.get("title", "")).strip()
        if not INTERNSHIP.search(title) or not data.get("id"):
            return None
        url = data.get("absolute_url", "")
        if urlparse(url).scheme != "https" or not urlparse(url).hostname:
            return None
        description = BeautifulSoup(html.unescape(html.unescape(data.get("content", ""))), "lxml").get_text(" ", strip=True)
        location = data.get("location", {}).get("name") or "Location not specified"
        if location.lower() in {"in-office", "in office"}:
            offices = ", ".join(office.get("location") or office.get("name", "") for office in data.get("offices", []))
            location = offices or location
        mode = "remote" if re.search(r"\bremote\b", location, re.I) else "hybrid" if re.search(r"\bhybrid\b", location, re.I) else "onsite"
        text = f"{title} {description}"
        skills = [label for pattern, label in [
            (r"\bpython\b", "Python"), (r"\bjava\b", "Java"), (r"\bjavascript\b", "JavaScript"),
            (r"\btypescript\b", "TypeScript"), (r"\breact\b", "React"), (r"\bsql\b", "SQL"),
            (r"\bc\+\+", "C++"), (r"\brust\b", "Rust"), (r"\bmachine learning\b", "Machine Learning"),
            (r"\bfigma\b", "Figma"), (r"\baws\b", "AWS"),
        ] if re.search(pattern, text, re.I)]
        domains = [label for pattern, label in [
            (r"software|engineer|developer", "Software Development"), (r"data|analytics", "Data Science"),
            (r"machine learning|\bai\b", "AI/ML"), (r"design", "UI/UX Design"),
            (r"product", "Product Management"), (r"marketing", "Marketing"),
        ] if re.search(pattern, title, re.I)]
        published = data.get("first_published")
        try:
            posted_date = date.fromisoformat(published[:10]) if published else None
        except (TypeError, ValueError):
            posted_date = None
        return ScrapedOpportunity(title=title[:300], company=company, description=description[:5000],
            source="greenhouse", source_id=f"{board}:{data['id']}", source_url=url[:1000],
            location=location[:300], work_mode=mode, skills_required=skills, domains=domains,
            posted_date=posted_date)
