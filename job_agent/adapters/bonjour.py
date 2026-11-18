from __future__ import annotations

import re

from bs4 import BeautifulSoup

from job_agent.adapters.base import PlatformAdapter
from job_agent.browser import BrowserSession
from job_agent.models import (
    AnswerSet,
    ApplicationForm,
    FormField,
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

    @staticmethod
    def parse_form(html: str) -> ApplicationForm:
        soup = BeautifulSoup(html, "html.parser")
        fields: list[FormField] = []

        for element in soup.select("textarea[name], input[name], select[name]"):
            name = element.get("name", "").strip()
            if not name:
                continue
            tag = element.name
            input_type = (element.get("type") or "text").lower()
            if tag == "textarea":
                kind = "textarea"
            elif tag == "select":
                kind = "select"
            elif input_type == "checkbox":
                kind = "checkbox"
            elif input_type == "file":
                kind = "file"
            else:
                kind = "text"

            label = ""
            if element.get("id"):
                label_el = soup.find("label", attrs={"for": element["id"]})
                if label_el:
                    label = label_el.get_text(" ", strip=True)
            required = element.has_attr("required") or label.endswith("*")
            fields.append(
                FormField(
                    name=name,
                    label=label.rstrip("*").strip(),
                    kind=kind,
                    required=required,
                    placeholder=element.get("placeholder", ""),
                )
            )

        buttons = [b.get_text(" ", strip=True) for b in soup.select("button")]
        already = BonjourAdapter.is_already_applied(html)
        submit_label = "申请职位" if "申请职位" in buttons else (buttons[-1] if buttons else "申请职位")
        attachments = [
            b.get_text(" ", strip=True)
            for b in soup.select("button.ap-work-item")
        ]

        return ApplicationForm(
            fields=fields,
            attachment_names=attachments,
            submit_label=submit_label,
            already_applied=already and "申请职位" not in buttons,
        )

    @staticmethod
    def detect_unknown_required(form: ApplicationForm, answers: AnswerSet) -> list[str]:
        known = set(answers.answers)
        known.add("message")
        return sorted(
            f.name
            for f in form.fields
            if f.required and f.name not in known and f.name not in {"", "message"}
        )

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
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")

        for attachment in answers.attachments:
            item = page.locator("button.ap-work-item").filter(has_text=attachment).first
            if item.count() and "is-selected" not in (item.get_attribute("class") or ""):
                item.click()

        for field in form.fields:
            selector = f'[name="{field.name}"]'
            value = answers.message if field.name == "message" else answers.answers.get(field.name, "")
            if not value and not field.required:
                continue
            if field.kind in {"text", "textarea"}:
                page.fill(selector, value)
            elif field.kind == "checkbox":
                page.set_checked(selector, value.strip().lower() in {"1", "true", "yes", "on"})
            elif field.kind == "select":
                page.select_option(selector, value)

    def submit(self, form: ApplicationForm) -> SubmissionResult:
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")

        apply_button = page.get_by_role("button", name="申请职位")
        if apply_button.count() == 0 and page.get_by_role("button", name="修改").count():
            return SubmissionResult(success=False, error="already_applied")

        apply_button.first.click()
        try:
            page.wait_for_url(re.compile(r"result=success"), timeout=15000)
            return SubmissionResult(success=True, url=page.url)
        except Exception as exc:  # noqa: BLE001 - report the platform state
            return SubmissionResult(success=False, url=page.url, error=str(exc))

    def application_status(self, platform: str, job_id: str) -> str:
        return "submitted"
