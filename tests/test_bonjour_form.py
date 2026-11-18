from pathlib import Path

from job_agent.adapters.bonjour import BonjourAdapter
from job_agent.models import AnswerSet

HTML = Path("tests/fixtures/bonjour_form.html").read_text(encoding="utf-8")


def test_parse_form_finds_message_and_custom_question():
    form = BonjourAdapter.parse_form(HTML)
    names = {f.name for f in form.fields}
    assert "message" in names
    assert "github" in names
    assert form.submit_label == "申请职位"


def test_unknown_required_question_is_reported():
    form = BonjourAdapter.parse_form(HTML)
    answers = AnswerSet(message="hi", answers={}, attachments=["cv"])
    assert BonjourAdapter.detect_unknown_required(form, answers) == ["github"]


def test_parse_form_detects_already_applied():
    form = BonjourAdapter.parse_form("<button>修改</button>")
    assert form.already_applied is True
