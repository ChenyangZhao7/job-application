from job_agent.models import AnswerSet
from job_agent.profile import Profile
from job_agent.writer.validation import validate_answer

PROFILE = Profile(
    name="Test",
    headline="Engineer",
    cv={"markdown": "cv.md", "pdf": "cv.pdf"},
    links={"github": "https://github.com/test"},
)

CLEAN = (
    "我想参与把 Agent 的记忆做稳，让它在真实场景里长期可用。"
    "我相信工具只有被真正使用才算成立，所以愿意从真实用户和失败案例里找问题，"
    "而不是停在演示。我也愿意把评测、上下文和工具调用这些脏活做扎实，"
    "让产品每天都能被打开，而不是只在发布时被看见。"
    "我希望和团队一起，把这件事从一个小原型推到真正有人依赖的产品。"
)


def test_banned_phrase_fails():
    a = AnswerSet(message="我想赋能这个行业，形成闭环。", answers={}, attachments=[])
    assert any("赋能" in r for r in validate_answer(a, PROFILE, "zh"))


def test_too_long_fails():
    a = AnswerSet(message="x" * 301, answers={}, attachments=[])
    assert any("length" in r for r in validate_answer(a, PROFILE, "zh"))


def test_clean_message_passes():
    a = AnswerSet(message=CLEAN, answers={}, attachments=[])
    assert validate_answer(a, PROFILE, "zh") == []


def test_empty_message_fails():
    a = AnswerSet(message="", answers={}, attachments=[])
    assert validate_answer(a, PROFILE, "zh") == ["empty message"]


def test_wrong_language_fails():
    a = AnswerSet(message="I want to build agent memory. " * 10, answers={}, attachments=[])
    assert any("language" in r for r in validate_answer(a, PROFILE, "zh"))


def test_memory_grounding_passes():
    a = AnswerSet(message=CLEAN + " 我在 Google 做过搜索。", answers={}, attachments=[])
    assert validate_answer(a, PROFILE, "zh", memory="Google") == []


def test_unsupported_claim_fails_grounding():
    a = AnswerSet(message="我在 Google 负责过搜索业务。", answers={}, attachments=[])
    assert any("grounding" in r for r in validate_answer(a, PROFILE, "zh"))
