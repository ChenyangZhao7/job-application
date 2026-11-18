from pathlib import Path

from typer.testing import CliRunner

from job_agent.cli import _make_writer, _resolve_auto, app
from job_agent.profile import Profile


def test_cli_help_lists_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output and "login" in result.output


def _profile(**kwargs):
    data = dict(
        name="Test",
        headline="Engineer",
        cv={"markdown": "cv.md", "pdf": "cv.pdf"},
        links={"github": "https://github.com/test"},
    )
    data.update(kwargs)
    return Profile(**data)


def test_resolve_auto_respects_allow_full_auto():
    assert _resolve_auto(True, _profile()) is True
    assert _resolve_auto(True, _profile(submission={"allow_full_auto": False})) is False
    assert _resolve_auto(False, _profile()) is False


def test_local_chat_writer_gets_separate_session(monkeypatch):
    class FakeSession:
        def __init__(self, path):
            self.path = Path(path)
            self.started = False

        def start(self):
            self.started = True

        def close(self):
            self.started = False

    class FakeWriter:
        def __init__(self, session, **kwargs):
            self.session = session

    monkeypatch.setattr("job_agent.cli.BrowserSession", FakeSession)
    monkeypatch.setattr("job_agent.cli.LocalChatWriter", FakeWriter)

    platform_session = FakeSession(".browser/bonjour")
    writer, writer_session = _make_writer("local_chat", _profile(), platform_session)
    assert writer_session is not platform_session
    assert writer_session is writer.session
    assert "writer-kimi" in str(writer_session.path)
