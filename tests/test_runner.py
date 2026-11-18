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

CLEAN = (
    "我想参与把 Agent 的记忆做稳，让它在真实场景里长期可用。"
    "我相信工具只有被真正使用才算成立，所以愿意从真实用户和失败案例里找问题，"
    "而不是停在演示。我也愿意把评测、上下文和工具调用这些脏活做扎实，"
    "让产品每天都能被打开，而不是只在发布时被看见。"
    "我希望和团队一起，把这件事从一个小原型推到真正有人依赖的产品。"
)
CLEAN2 = CLEAN + "我也愿意从最基础的事情做起。"

JOB = Job(
    id="j1",
    platform="fake",
    title="AI Agent 实习",
    company="C",
    location="远程",
    url="https://example.com/j1",
    description="Python Agent 记忆",
)
DETAIL = JobDetail(job=JOB)
FORM = ApplicationForm(
    job=JOB,
    fields=[FormField(name="message", kind="textarea")],
    submit_label="申请职位",
)
RESULT = SubmissionResult(success=True)
ANSWER = AnswerSet(message=CLEAN, answers={}, attachments=[])
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

    def ensure_login(self):
        return None

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
    memory = ""

    def __init__(self, message=CLEAN):
        self.message = message

    def generate(self, *args, **kwargs):
        return AnswerSet(message=self.message, answers={}, attachments=[])


def test_runner_does_not_submit_in_dry_run(tmp_path: Path, capsys):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, dry_run=True)
    report = r.run()
    assert report.submitted == 0 and adapter.filled is not None
    assert CLEAN in capsys.readouterr().out


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


def test_runner_skips_empty_writer_output(tmp_path: Path):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(message=""), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1


def test_runner_skips_banned_phrase(tmp_path: Path):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(
        adapter,
        FakeWriter(message="我想赋能这个行业，形成闭环。" * 10),
        tracker,
        PROFILE,
        auto=True,
    )
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1


def test_runner_skips_wrong_language(tmp_path: Path):
    english = "I want to build agent memory that people actually use every day. " * 10
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(message=english), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1


def test_runner_prompts_for_unknown_question(tmp_path: Path):
    adapter = FakeAdapter()
    adapter.open_application = lambda job: ApplicationForm(
        job=JOB,
        fields=[FormField(name="github", kind="textarea", required=True)],
        submit_label="申请职位",
    )
    adapter.detect_unknown_required = lambda form, answers: (
        [] if answers.answers.get("github") else ["github"]
    )
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(
        adapter,
        FakeWriter(),
        tracker,
        PROFILE,
        auto=False,
        approval_fn=lambda **_: Decision.SUBMIT,
        input_fn=lambda _: "https://github.com/test",
    )
    report = r.run()
    assert report.submitted == 1
    assert adapter.filled.answers["github"] == "https://github.com/test"


def test_runner_records_unknown_submission(tmp_path: Path):
    adapter = FakeAdapter()
    adapter.submit = lambda form: SubmissionResult(success=False, error="unknown")
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.unknown == 1
    assert len(tracker.list("unknown")) == 1


def test_runner_continues_after_adapter_error(tmp_path: Path):
    adapter = FakeAdapter()

    def explode(job):
        raise RuntimeError("selector missing")

    adapter.get_job = explode
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(adapter, FakeWriter(), tracker, PROFILE, auto=True)
    report = r.run()
    assert report.failed == 1


def test_runner_edit_decision_submits_edited_message(tmp_path: Path):
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    r = Runner(
        adapter,
        FakeWriter(),
        tracker,
        PROFILE,
        auto=False,
        approval_fn=lambda **_: Decision.EDIT,
        input_fn=lambda _: CLEAN2,
    )
    report = r.run()
    assert report.submitted == 1
    assert adapter.filled.message == CLEAN2


def test_runner_calls_ensure_login(tmp_path: Path):
    adapter = FakeAdapter()
    calls = {"n": 0}
    adapter.ensure_login = lambda: calls.__setitem__("n", calls["n"] + 1)
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    Runner(adapter, FakeWriter(), tracker, PROFILE, auto=True).run()
    assert calls["n"] >= 1


def test_runner_merges_profile_answers_and_attachments(tmp_path: Path):
    profile = PROFILE.model_copy(update={"answers": {"availability": "now"}})
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    Runner(adapter, FakeWriter(), tracker, profile, auto=True).run()
    assert adapter.filled.answers["availability"] == "now"
    assert "cv" in adapter.filled.attachments
    assert "github" in adapter.filled.attachments


def test_runner_skips_below_min_score(tmp_path: Path):
    profile = PROFILE.model_copy(deep=True)
    profile.preferences.min_score = 101
    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    report = Runner(adapter, FakeWriter(), tracker, profile, auto=True).run()
    assert report.submitted == 0 and report.skipped == 1


def test_runner_caps_limit_by_max_per_run(tmp_path: Path):
    job2 = JOB.model_copy(update={"id": "j2", "url": "https://example.com/j2"})
    adapter = FakeAdapter()
    adapter.search = lambda filters: [JOB, job2]
    profile = PROFILE.model_copy(deep=True)
    profile.preferences.max_per_run = 1
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    report = Runner(adapter, FakeWriter(), tracker, profile, auto=True, limit=10).run()
    assert report.submitted + report.skipped == 1


def test_runner_retries_invalid_draft_once(tmp_path: Path):
    class SequenceWriter(FakeWriter):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            message = "" if self.calls == 1 else CLEAN
            return AnswerSet(message=message, answers={}, attachments=[])

    adapter = FakeAdapter()
    tracker = Tracker(tmp_path / "db.sqlite")
    tracker.init()
    writer = SequenceWriter()
    report = Runner(adapter, writer, tracker, PROFILE, auto=True).run()
    assert report.submitted == 1 and writer.calls >= 2


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
