from job_agent.matcher import score_job
from job_agent.models import Job
from job_agent.profile import Profile

PROFILE = Profile(
    name="Test",
    headline="AI Agent Engineer",
    cv={"markdown": "cv.md", "pdf": "cv.pdf"},
    links={"github": "https://github.com/test"},
    preferences={
        "job_types": ["internship"],
        "exclude_keywords": ["HR"],
        "allow_external_redirect": False,
        "locations": ["remote", "Beijing"],
    },
)


def job(**kw):
    base = dict(
        id="j1",
        platform="bonjour",
        title="AI Agent Intern",
        company="C",
        location="Remote",
        url="https://x/j1",
        description="Python Agent memory",
        external_redirect=False,
    )
    base.update(kw)
    return Job(**base)


def test_excludes_hr():
    r = score_job(job(title="HR Intern"), PROFILE)
    assert r.excluded is True


def test_excludes_external_redirect_when_disallowed():
    r = score_job(job(external_redirect=True), PROFILE)
    assert r.excluded is True


def test_scores_matching_job_above_threshold():
    r = score_job(job(), PROFILE)
    assert r.excluded is False and r.score >= 60


def test_excludes_non_internship():
    r = score_job(job(title="Senior Engineer"), PROFILE)
    assert r.excluded is True
