from pathlib import Path

from job_agent.writer.local_chat import extract_chat_answer

HTML = Path("tests/fixtures/kimi_chat.html").read_text(encoding="utf-8")


def test_extract_chat_answer_ignores_prompt_and_copy_buttons():
    assert extract_chat_answer(HTML) == "这是生成的回答。"


def test_extract_chat_answer_returns_empty_when_missing():
    assert extract_chat_answer("<html></html>") == ""
