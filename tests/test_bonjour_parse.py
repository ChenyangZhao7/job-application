from pathlib import Path

from job_agent.adapters.bonjour import BonjourAdapter

FIXTURE = Path("tests/fixtures/bonjour_jobs.html").read_text(encoding="utf-8")


def test_parse_jobs_returns_cards():
    jobs = BonjourAdapter.parse_jobs(FIXTURE)
    assert [j.title for j in jobs] == ["Intern A", "Intern B"]
    assert jobs[0].external_redirect is False
    assert jobs[1].external_redirect is True


def test_parse_jobs_skips_hr_roles():
    jobs = BonjourAdapter.parse_jobs(FIXTURE)
    assert all("HR" not in j.title for j in jobs)


def test_is_already_applied_detects_modify_button():
    assert BonjourAdapter.is_already_applied("<button>修改</button>") is True
    assert BonjourAdapter.is_already_applied("<button>申请职位</button>") is False


def test_ensure_login_pauses_on_login_wall():
    class FakePage:
        url = "https://bonjour.bio/login"

        def inner_text(self, selector):
            return "登录后继续"

    class FakeSession:
        page = FakePage()
        paused = False

        def pause_for_login(self, message):
            self.paused = True

    session = FakeSession()
    BonjourAdapter(session).ensure_login()
    assert session.paused is True
