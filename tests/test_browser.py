from pathlib import Path

from job_agent.browser import BrowserSession


def test_session_can_render_and_screenshot(tmp_path: Path):
    s = BrowserSession(tmp_path / "profile", headless=True)
    s.start()
    s.page.set_content("<html><body><h1>Login</h1></body></html>")
    out = s.screenshot(tmp_path / "shot.png")
    assert out.exists() and out.stat().st_size > 0
    s.close()


def test_pause_for_login_saves_screenshot(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    s = BrowserSession(tmp_path / "profile", headless=True)
    s.start()
    s.page.set_content("<html><body>CAPTCHA</body></html>")
    s.pause_for_login("Log in, then press Enter")
    assert (tmp_path / "profile" / "login.png").exists()
    s.close()
