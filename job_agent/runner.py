from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from job_agent.approval import Decision, review
from job_agent.matcher import score_job
from job_agent.models import ApplicationRecord, JobFilters
from job_agent.profile import Profile
from job_agent.tracker import Tracker
from job_agent.writer.validation import detect_language, validate_answer


@dataclass
class RunReport:
    submitted: int = 0
    drafted: int = 0
    skipped: int = 0
    failed: int = 0
    unknown: int = 0
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
        input_fn: Callable[[str], str] = input,
    ):
        self.adapter = adapter
        self.writer = writer
        self.tracker = tracker
        self.profile = profile
        self.dry_run = dry_run
        self.auto = auto
        self.limit = limit
        self.approval_fn = approval_fn
        self.input_fn = input_fn

    def _record(
        self,
        job,
        match,
        status: str,
        message: str = "",
    ) -> None:
        try:
            self.tracker.record(
                ApplicationRecord(
                    platform=job.platform,
                    job_id=job.id,
                    company=job.company,
                    title=job.title,
                    url=job.url,
                    score=match.score if match else 0,
                    message=message,
                    status=status,
                    submitted_at=datetime.now(timezone.utc).isoformat(),
                    writer_backend=getattr(self.writer, "backend", ""),
                    provider=getattr(self.writer, "provider", ""),
                    memory_version=getattr(self.writer, "memory_version", ""),
                )
            )
        except Exception:
            pass

    def _validate(self, answer, detail) -> list[str]:
        language = detect_language(detail, self.profile)
        memory = getattr(self.writer, "memory", "")
        return validate_answer(answer, self.profile, language, memory)

    def _draft(self, detail, questions) -> tuple[object | None, list[str]]:
        answer = self.writer.generate(detail, self.profile, questions=questions)
        if answer is None:
            return None, ["writer returned no valid draft"]
        answer = answer.model_copy(
            update={
                "answers": {**self.profile.answers, **answer.answers},
                "attachments": ["cv"]
                + (["github"] if self.profile.links.github else []),
            }
        )
        reasons = self._validate(answer, detail)
        if reasons:
            retry = self.writer.generate(detail, self.profile, questions=questions)
            if retry is not None:
                retry = retry.model_copy(
                    update={
                        "answers": {**self.profile.answers, **retry.answers},
                        "attachments": ["cv"]
                        + (["github"] if self.profile.links.github else []),
                    }
                )
                retry_reasons = self._validate(retry, detail)
                if not retry_reasons:
                    return retry, []
                answer, reasons = retry, retry_reasons
        return answer, reasons

    def run(self) -> RunReport:
        report = RunReport()
        ensure_login = getattr(self.adapter, "ensure_login", None)
        if callable(ensure_login):
            ensure_login()

        filters = JobFilters(
            job_types=self.profile.preferences.job_types,
            exclude_keywords=self.profile.preferences.exclude_keywords,
            allow_external_redirect=self.profile.preferences.allow_external_redirect,
            locations=self.profile.preferences.locations,
            min_score=self.profile.preferences.min_score,
        )
        jobs = self.adapter.search(filters)
        limit = min(self.limit, self.profile.preferences.max_per_run, 10)

        for job in jobs[:limit]:
            try:
                if self.tracker.exists(job.platform, job.id):
                    report.skipped += 1
                    continue

                match = score_job(job, self.profile)
                if match.excluded or match.score < self.profile.preferences.min_score:
                    self._record(job, match, "skipped")
                    report.skipped += 1
                    continue

                detail = self.adapter.get_job(job)
                if callable(ensure_login):
                    ensure_login()
                form = self.adapter.open_application(job)
                if form.already_applied:
                    self._record(job, match, "already_applied")
                    report.skipped += 1
                    continue

                questions = [
                    f.name for f in form.fields if f.required and f.name != "message"
                ]
                answer, reasons = self._draft(detail, questions)
                if answer is None or reasons:
                    if self.auto:
                        self._record(job, match, "skipped_invalid", answer.message if answer else "")
                        report.skipped += 1
                        continue
                    replacement = self.input_fn(
                        "Draft failed validation: "
                        + "; ".join(reasons)
                        + "\nEnter a replacement message (blank to skip): "
                    )
                    if not replacement.strip():
                        self._record(job, match, "skipped_invalid")
                        report.skipped += 1
                        continue
                    answer = answer.model_copy(update={"message": replacement})
                    reasons = self._validate(answer, detail)
                    if reasons:
                        self._record(job, match, "skipped_invalid", answer.message)
                        report.failed += 1
                        continue

                unknown = self.adapter.detect_unknown_required(form, answer)
                if unknown:
                    if self.auto:
                        self._record(job, match, "skipped_unknown")
                        report.skipped += 1
                        continue
                    for question in list(unknown):
                        value = self.input_fn(f"Answer required question '{question}': ")
                        if not value.strip():
                            break
                        answer.answers[question] = value
                    unknown = self.adapter.detect_unknown_required(form, answer)
                    if unknown:
                        self._record(job, match, "skipped_unknown")
                        report.skipped += 1
                        continue

                self.adapter.fill(form, answer)

                if self.dry_run:
                    print(f"\n--- {job.company} — {job.title}")
                    print(answer.message)
                    print(f"Attachments: {', '.join(answer.attachments)}")
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
                    if decision == Decision.SKIP:
                        self._record(job, match, "skipped")
                        report.skipped += 1
                        continue
                    if decision == Decision.EDIT:
                        replacement = self.input_fn("New message: ")
                        if not replacement.strip():
                            self._record(job, match, "skipped")
                            report.skipped += 1
                            continue
                        answer = answer.model_copy(update={"message": replacement})
                        reasons = self._validate(answer, detail)
                        if reasons:
                            self._record(job, match, "skipped_invalid", answer.message)
                            report.failed += 1
                            continue
                        self.adapter.fill(form, answer)

                result = self.adapter.submit(form)
                if not result.success:
                    if result.error == "unknown":
                        self._record(job, match, "unknown", answer.message)
                        report.unknown += 1
                    else:
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

            except Exception as exc:  # noqa: BLE001 - keep the batch alive
                report.failed += 1
                session = getattr(self.adapter, "session", None)
                page = getattr(session, "page", None)
                if page is not None:
                    try:
                        target = Path("data/screenshots") / f"{job.id}.png"
                        page.screenshot(path=str(target), full_page=True)
                    except Exception:
                        pass
                print(f"adapter error on {job.company} — {job.title}: {exc}")

        return report
