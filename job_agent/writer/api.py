from __future__ import annotations

from pathlib import Path

from job_agent.models import AnswerSet, JobDetail
from job_agent.profile import Profile
from job_agent.writer.validation import parse_writer_json

DEFAULT_PROMPT = """You write a short, first-person message to a hiring team.

Job: {job_title} at {company}
Location: {location}
Job description:
{job_description}

Candidate profile (JSON):
{profile}

Long-term themes / memory pack:
{memory}

Questions to answer (JSON keys are question ids):
{questions}

Rules:
- Write in {language}.
- 150-300 Chinese characters (or 80-200 English words).
- Do not list CV projects; the CV already has them.
- Use concrete, high-level thinking; no slogans, no parallelism, no "赋能/闭环/生态".
- Avoid "正是我想体验的", "让数据说话", "如果有机会".
- Every factual claim must be supported by the profile or memory pack.
- Return JSON only: {{"message": "...", "answers": {{"question_id": "..."}}}}.
"""


def _language(detail: JobDetail, profile: Profile) -> str:
    if profile.style.language in {"zh", "en"}:
        return profile.style.language
    text = f"{detail.job.title} {detail.job.description} {detail.requirements}"
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return "zh" if cjk > len(text) * 0.3 else "en"


class ApiWriter:
    def __init__(
        self,
        client,
        model: str,
        prompt_path: Path | None = None,
        max_chars: int = 300,
        memory: str = "",
    ):
        self.client = client
        self.model = model
        self.prompt_path = prompt_path
        self.max_chars = max_chars
        self.memory = memory
        self.backend = "api"
        self.provider = model
        self.memory_version = ""

    def _template(self) -> str:
        if self.prompt_path and Path(self.prompt_path).exists():
            return Path(self.prompt_path).read_text(encoding="utf-8")
        return DEFAULT_PROMPT

    def build_prompt(
        self,
        detail: JobDetail,
        profile: Profile,
        memory: str,
        questions: list[str],
    ) -> str:
        return self._template().format(
            job_title=detail.job.title,
            company=detail.job.company,
            location=detail.job.location,
            job_description=detail.job.description or detail.requirements,
            profile=profile.model_dump_json(indent=2)[:6000],
            memory=memory,
            questions=questions,
            language=_language(detail, profile),
            max_chars=self.max_chars,
        )

    def generate(
        self,
        detail: JobDetail,
        profile: Profile,
        memory: str = "",
        questions: list[str] | None = None,
    ) -> AnswerSet:
        prompt = self.build_prompt(detail, profile, memory or self.memory, questions or [])
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        data = parse_writer_json(raw)
        if data is None:
            return AnswerSet(message="", answers={}, attachments=[])
        message = str(data.get("message", ""))[: self.max_chars]
        answers = data.get("answers", {})
        if not isinstance(answers, dict):
            answers = {}
        return AnswerSet(
            message=message,
            answers={str(k): str(v) for k, v in answers.items()},
            attachments=[],
        )
