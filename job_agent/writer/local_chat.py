from __future__ import annotations

from bs4 import BeautifulSoup

from job_agent.browser import BrowserSession
from job_agent.models import AnswerSet, JobDetail
from job_agent.profile import Profile
from job_agent.writer.validation import detect_language

PROVIDER_URLS = {
    "kimi": "https://www.kimi.com/",
    "doubao": "https://www.doubao.com/chat/",
    "chatgpt": "https://chatgpt.com/",
}


def extract_chat_answer(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select(
        ".message.assistant .markdown, [data-role='assistant'] .markdown, .assistant .markdown"
    )
    if not candidates:
        return ""
    node = candidates[-1]
    for button in node.find_all("button"):
        button.decompose()
    return node.get_text(" ", strip=True).strip()


class LocalChatWriter:
    """Generate a message by driving the user's logged-in chat UI.

    This backend uses the account's own memory. It opens a fresh
    conversation per job and never reuses the previous one.
    """

    def __init__(
        self,
        session: BrowserSession,
        provider: str = "kimi",
        fresh_conversation_per_job: bool = True,
    ):
        if provider not in PROVIDER_URLS:
            raise ValueError(f"unsupported local-chat provider: {provider}")
        self.session = session
        self.provider = provider
        self.fresh_conversation_per_job = fresh_conversation_per_job
        self.backend = "local_chat"
        self.memory_version = "account"

    def _build_prompt(self, detail: JobDetail, profile: Profile, questions: list[str]) -> str:
        language = detect_language(detail, profile)
        if language == "en":
            return (
                "Write a 80-200 word first-person message to the hiring team.\n"
                "Do not list CV projects; use high-level, concrete thinking; no slogans.\n"
                "Every factual claim must come from the profile below.\n\n"
                f"Role: {detail.job.title} at {detail.job.company}\n"
                f"Location: {detail.job.location}\n"
                f"Description: {detail.job.description or detail.requirements}\n\n"
                f"Profile:\n{profile.model_dump_json(indent=2)[:5000]}\n\n"
                f"Questions: {questions}\n\n"
                "Output only the message."
            )
        return (
            "请写一段给招聘团队的话，中文，150-300 字。\n"
            "要求：第一人称；不要罗列简历项目；高概念、具体；"
            "不要口号、排比、'赋能/闭环/生态'；"
            "不要'正是我想体验的''让数据说话''如果有机会'；"
            "所有关于我的事实必须来自下面的资料。\n\n"
            f"岗位：{detail.job.title} @ {detail.job.company}\n"
            f"地点：{detail.job.location}\n"
            f"岗位描述：{detail.job.description or detail.requirements}\n\n"
            f"我的资料：\n{profile.model_dump_json(indent=2)[:5000]}\n\n"
            f"需要回答的问题：{questions}\n\n"
            "只输出这段话本身。"
        )

    def generate(
        self,
        detail: JobDetail,
        profile: Profile,
        questions: list[str] | None = None,
    ) -> AnswerSet | None:
        page = self.session.page
        if page is None:
            raise RuntimeError("browser session is not started")

        page.goto(PROVIDER_URLS[self.provider], wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        login_markers = ("Phone number", "Log in to sync chat history", "登录", "扫码")
        if any(marker in body for marker in login_markers) and "Ask anything" not in body:
            self.session.pause_for_login(f"Log in to {self.provider}, then press Enter")

        editor = page.locator(".chat-input-editor").first
        editor.wait_for(timeout=30000)
        prompt = self._build_prompt(detail, profile, questions or [])
        editor.click()
        page.evaluate(
            """(text) => {
                const el = document.querySelector('.chat-input-editor');
                el.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, text);
            }""",
            prompt,
        )
        send = page.locator(".send-button-container").first
        send.click()

        for _ in range(120):
            text = page.inner_text("body")
            if "Working" not in text and "停止" not in text and "Thinking" not in text:
                break
            page.wait_for_timeout(1000)

        answer = extract_chat_answer(page.content())
        if not answer:
            return None
        return AnswerSet(message=answer, answers={}, attachments=[])
