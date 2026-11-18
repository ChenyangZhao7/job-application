from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from job_agent.approval import Decision, review
from job_agent.matcher import score_job
from job_agent.models import ApplicationRecord, JobFilters
from job_agent.profile import Profile
from job_agent.tracker import Tracker


@dataclass
class RunReport:
    submitted: int = 0
    drafted: int = 0
    skipped: int = 0
    failed: int = 0
    applications: list[ApplicationRecord] = field(default_factory=list)


class Runner:
    def __init__(
        self,
        adapter,
        writer,
        tracker: Tracker,
        profile: Profile,
        dry_run: bool = False,
        auto: bool = False,
        limit: int = 10,
        approval_fn: Callable[..., Decision] = review,
    ):
        self.adapter = adapter
        self.writer = writer
        self.tracker = tracker
        self.profile = profile
        self.dry_run = dry_run
        self.auto = auto
        self.limit = limit
        self.approval_fn = approval_fn

    def run(self) -> RunReport:
        report = RunReport()
        filters = JobFilters(
            job_types=self.profile.preferences.job_types,
            exclude_keywords=self.profile.preferences.exclude_keywords,
            allow_external_redirect=self.profile.preferences.allow_external_redirect,
            locations=self.profile.preferences.locations,
        )
        jobs = self.adapter.search(filters)

        for job in jobs[: self.limit]:
            if self.tracker.exists(job.platform, job.id):
                report.skipped += 1
                continue

            match = score_job(job, self.profile)
            if match.excluded:
                report.skipped += 1
                continue

            detail = self.adapter.get_job(job)
            form = self.adapter.open_application(job)
            if form.already_applied:
                report.skipped += 1
                continue

            questions = [
                f.name for f in form.fields if f.required and f.name != "message"
            ]
            answer = self.writer.generate(detail, self.profile, questions=questions)
            unknown = self.adapter.detect_unknown_required(form, answer)
            if unknown:
                # Never submit a form with an unanswered required question.
                report.skipped += 1
                continue

            self.adapter.fill(form, answer)
            if self.dry_run:
                report.drafted += 1
                continue

            if not self.auto:
                decision = self.approval_fn(
                    job_title=job.title,
                    company=job.company,
                    score=match.score,
                    message=answer.message,
                    attachments=answer.attachments,
                    unknown_questions=unknown,
                )
                if decision == Decision.QUIT:
                    break
                if decision in {Decision.SKIP, Decision.EDIT}:
                    report.skipped += 1
                    continue

            result = self.adapter.submit(form)
            if not result.success:
                report.failed += 1
                continue

            record = ApplicationRecord(
                platform=job.platform,
                job_id=job.id,
                company=job.company,
                title=job.title,
                url=job.url,
                score=match.score,
                message=answer.message,
                status="submitted",
                submitted_at=datetime.now(timezone.utc).isoformat(),
                writer_backend=getattr(self.writer, "backend", ""),
                provider=getattr(self.writer, "provider", ""),
                memory_version=getattr(self.writer, "memory_version", ""),
            )
            self.tracker.record(record)
            report.applications.append(record)
            report.submitted += 1

        return report
