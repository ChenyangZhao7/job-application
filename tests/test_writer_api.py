from types import SimpleNamespace

from job_agent.models import Job, JobDetail
from job_agent.profile import Profile
from job_agent.writer.api import ApiWriter, parse_writer_json


def test_parse_writer_json_strips_fences():
    raw = '```json\n{"message":"hi","answers":{}}\n```'
    assert parse_writer_json(raw)["message"] == "hi"


def test_parse_writer_json_rejects_invalid():
    assert parse_writer_json("not json") is None


class FakeClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            ))
        )


def _detail_and_profile():
    detail = JobDetail(job=Job(
        id="j1", platform="bonjour", title="AI Intern", company="C",
        location="Remote", url="https://example.com/j1",
    ))
    profile = Profile(
        name="Test", headline="Engineer",
        cv={"markdown": "cv.md", "pdf": "cv.pdf"},
        links={"github": "https://github.com/test"},
    )
    return detail, profile


def test_api_writer_generate_returns_answer():
    detail, profile = _detail_and_profile()
    writer = ApiWriter(FakeClient('{"message":"hi","answers":{}}'), model="deepseek-chat", prompt_path=None)
    answer = writer.generate(detail, profile, memory="", questions=[])
    assert answer.message == "hi"


def test_api_writer_invalid_json_returns_none():
    detail, profile = _detail_and_profile()
    writer = ApiWriter(FakeClient("not json"), model="deepseek-chat", prompt_path=None)
    assert writer.generate(detail, profile, memory="", questions=[]) is None
