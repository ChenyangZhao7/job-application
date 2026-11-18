from pathlib import Path

from job_agent.adapters.bonjour import BonjourAdapter
from job_agent.browser import BrowserSession
from job_agent.models import AnswerSet

HTML = Path("tests/fixtures/mock_bonjour.html").read_text(encoding="utf-8")


def test_mock_form_fill_and_submit_contract():
    form = BonjourAdapter.parse_form(HTML)
    assert "message" in {f.name for f in form.fields}
    assert (
        BonjourAdapter.detect_unknown_required(
            form,
            AnswerSet(
                message="hi",
                answers={"github": "https://github.com/test"},
                attachments=[],
            ),
        )
        == []
    )


def test_mock_form_fill_sets_values(tmp_path: Path):
    s = BrowserSession(tmp_path / "p", headless=True)
    s.start()
    s.page.set_content(HTML)
    form = BonjourAdapter.parse_form(HTML)
    BonjourAdapter(s).fill(
        form,
        AnswerSet(
            message="hi",
            answers={"github": "https://github.com/test"},
            attachments=["cv", "github"],
        ),
    )
    assert s.page.input_value("textarea[name=message]") == "hi"
    assert s.page.input_value("textarea[name=github]") == "https://github.com/test"
    assert "is-selected" in (
        s.page.locator("button.ap-work-item").nth(1).get_attribute("class") or ""
    )
    s.close()
