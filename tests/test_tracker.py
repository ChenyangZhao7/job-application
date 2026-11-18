from datetime import datetime, timedelta, timezone
from pathlib import Path

from job_agent.models import ApplicationRecord
from job_agent.tracker import Tracker


def make_record(job_id="j1", status="submitted"):
    return ApplicationRecord(
        platform="bonjour",
        job_id=job_id,
        company="C",
        title="T",
        url=f"https://example.com/{job_id}",
        score=80,
        message="hi",
        status=status,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        writer_backend="api",
        provider="deepseek",
        memory_version="1",
    )


def test_record_and_exists(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    assert t.exists("bonjour", "j1") is False
    t.record(make_record())
    assert t.exists("bonjour", "j1") is True


def test_duplicate_record_is_ignored(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    t.record(make_record())
    t.record(make_record())
    assert len(t.list()) == 1


def test_clear_skipped_keeps_submitted(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    t.record(make_record("submitted", status="submitted"))
    t.record(make_record("skipped", status="skipped"))
    t.record(make_record("already", status="already_applied"))
    t.clear_skipped()
    assert [r.job_id for r in t.list()] == ["submitted"]


def test_mark_and_follow_ups(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    old = make_record("j2")
    old.submitted_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    t.record(old)
    t.mark("bonjour", "j2", "replied")
    assert t.list("replied")[0].job_id == "j2"
    assert [r.job_id for r in t.follow_ups(7)] == []
