from __future__ import annotations

from bs4 import BeautifulSoup

from job_agent.adapters.base import PlatformAdapter
from job_agent.browser import BrowserSession
from job_agent.models import (
    AnswerSet,
    ApplicationForm,
    Job,
    JobDetail,
    JobFilters,
    SubmissionResult,
)

BASE_URL = "https://bonjour.bio"
JOBS_URL = f"{BASE_URL}/jobs-mapping/jobs"


class BonjourAdapter(PlatformAdapter):
    name = "bonjour"

    def __init__(self, session: BrowserSession):
        self.session = session

    # -- parsing ---------------------------------------------------------

    @staticmethod
    def parse_jobs(html: str) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        seen: set[str] = set()

        for anchor in soup.select('a[href*="/jobs-mapping/jobs/"]'):
            href = anchor.get("href", "")
            if "/apply" in href:
                continue
            job_id = href.split("/jobs-mapping/jobs/", 1)[-1].split("?", 1)[0]
            if not job_id or job_id in seen:
                continue

            card = anchor.find_parent(class_="job-card") or anchor.parent
            if card is None:
                continue

            title_el = card.select_one(".job-title")
            company_el = card.select_one(".company")
            location_el = card.select_one(".location")
            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = location_el.get_text(strip=True) if location_el else ""
            if not title:
                continue
            if "HR" in title or "人力资源" in title:
                continue

            external = card.select_one(".external") is not None
            if href.startswith("http") and "bonjour.bio" not in href:
                external = True

            jobs.append(
                Job(
                    id=job_id,
                    platform="bonjour",
                    title=title,
                    company=company or "Unknown",
                    location=location,
                    tags=[],
                    url=f"{BASE_URL}{href}" if href.startswith("/") else href,
                    description=card.get_text(" ", strip=True),
                    external_redirect=external,
                )
            )
            seen.add(job_id)

        return jobs

    @staticmethod
    def is_already_applied(html: str) -> bool:
        return "修改" in html

    # -- adapter ---------------------------------------------------------

    def login(self) -> None:
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        self.session.pause_for_login("Log in to Bonjour, then press Enter")

    def search(self, filters: JobFilters) -> list[Job]:
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")
        page.goto(JOBS_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        return self.parse_jobs(page.content())

    def get_job(self, job: Job) -> JobDetail:
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")
        page.goto(job.url, wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        text = page.inner_text("body")
        return JobDetail(job=job, company_description="", requirements=text)

    def open_application(self, job: Job) -> ApplicationForm:
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")
        url = job.url.rstrip("/") + "/apply?src=list"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        return self.parse_form(page.content())

    def fill(self, form: ApplicationForm, answers: AnswerSet) -> None:
        raise NotImplementedError

    def submit(self, form: ApplicationForm) -> SubmissionResult:
        raise NotImplementedError

    def application_status(self, platform: str, job_id: str) -> str:
        return "submitted"
