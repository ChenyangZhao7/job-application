from datetime import datetime, timezone
from pathlib import Path

from job_agent.approval import Decision, review
from job_agent.models import (
    AnswerSet,
    ApplicationForm,
    ApplicationRecord,
    FormField,
    Job,
    JobDetail,
    SubmissionResult,
)
from job_agent.profile import Profile
from job_agent.runner import Runner
from job_agent.tracker import Tracker

JOB = Job(
    id="j1",
    platform="fake",
    title="AI Agent Intern",
    company="C",
    location="Remote",
    url="https://example.com/j1",
    description="Python Agent memory",
)
DETAIL = JobDetail(job=JOB)
FORM = ApplicationForm(
    job=JOB,
    fields=[FormField(name="message", kind="textarea")],
    submit_label="申请职位",
)
RESULT = SubmissionResult(success=True)
ANSWER = AnswerSet(message="hi", answers={}, attachments=[])
PROFILE = Profile(
    name="Test",
    headline="AI Agent Engineer",
    cv={"markdown": "cv.md", "pdf": "cv.pdf"},
    links={"github": "https://github.com/test"},
    preferences={
        "job_types": ["internship"],
        "exclude_keywords": ["HR"],
        "allow_external_redirect": False,
        "locations": ["remote"],
    },
)


def make_record(job_id="j1"):
    return ApplicationRecord(
        platform="fake",
        job_id=job_id,
        company="C",
        title="T",
        url=f"https://example.com/{job_id}",
        score=80,
        message="hi",
        status="submitted",
        submitted_at=datetime.now(timezone.utc).isoformat(),
        writer_backend="api",
        provider="deepseek",
        memory_version="1",
    )


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.filled = None

    def login(self):
        return None

    def search(self, filters):
        return [JOB]

    def get_job(self, job):
        return DETAIL

    def open_application(self, job):
        return FORM

    def detect_unknown_required(self, form, answers):
        return []

    def fill(self, form, answers):
        self.filled = answers

    def submit(self, form):
        return RESULT

    def application_status(self, platform, job_id):
        return "submitted"


class FakeWriter:
    backend = "api"
    provider = "deepseek"
    memory_version = "1"

    def generate(self, *args, **kwargs):
        return ANSWER


def test_runner_does_not_submit_in_dry_run(tmp_path: Path):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, dry_run=True)
    report = r.run()
    assert report.submitted == 0 and adapter.filled is not None


def test_runner_submits_after_approval(tmp_path: Path):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.submitted == 1


def test_runner_skips_unknown_required_question_in_auto_mode(tmp_path: Path):
    adapter = FakeAdapter()
    adapter.open_application = lambda job: ApplicationForm(
        job=JOB,
        fields=[FormField(name="github", kind="textarea", required=True)],
        submit_label="申请职位",
    )
    adapter.detect_unknown_required = lambda form, answers: ["github"]
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1


def test_runner_skips_already_submitted_job(tmp_path: Path):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    tracker.record(make_record("j1"))
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1


def test_review_returns_skip():
    decision = review(
        job_title="T",
        company="C",
        score=80,
        message="hi",
        attachments=[],
        unknown_questions=[],
        input_fn=lambda _: "n",
    )
    assert decision == Decision.SKIP
