import pytest
from pydantic import ValidationError

from job_agent.models import Job


def test_job_requires_id_and_url():
    job = Job(
        id="j1",
        platform="bonjour",
        title="T",
        company="C",
        location="Remote",
        url="https://example.com/j1",
    )
    assert job.external_redirect is False


def test_job_rejects_empty_id():
    with pytest.raises(ValidationError):
        Job(
            id="",
            platform="bonjour",
            title="T",
            company="C",
            location="Remote",
            url="https://example.com/j1",
        )
