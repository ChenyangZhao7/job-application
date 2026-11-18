from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Links(BaseModel):
    github: str = Field(min_length=1)
    email: str = ""
    phone: str = ""


class CV(BaseModel):
    markdown: str = Field(min_length=1)
    pdf: str = Field(min_length=1)


class Education(BaseModel):
    school: str
    degree: str
    period: str


class Preferences(BaseModel):
    job_types: list[str] = Field(default_factory=lambda: ["internship"])
    exclude_keywords: list[str] = Field(default_factory=list)
    allow_external_redirect: bool = False
    locations: list[str] = Field(default_factory=list)
    max_per_run: int = 10
    min_score: int = 60


class WriterApiConfig(BaseModel):
    provider: str = "deepseek"
    base_url_env: str = "JOB_AGENT_LLM_BASE_URL"
    api_key_env: str = "JOB_AGENT_LLM_API_KEY"
    model: str = "deepseek-chat"


class WriterLocalChatConfig(BaseModel):
    provider: str = "kimi"
    use_account_memory: bool = True
    fresh_conversation_per_job: bool = True


class WriterConfig(BaseModel):
    backend: str = "api"
    api: WriterApiConfig = Field(default_factory=WriterApiConfig)
    local_chat: WriterLocalChatConfig = Field(default_factory=WriterLocalChatConfig)
    memory_profile: str = "config/memory.md"
    max_chars: int = 300


class SubmissionConfig(BaseModel):
    require_approval: bool = True
    allow_full_auto: bool = True


class StyleConfig(BaseModel):
    language: str = "auto"
    length: str = "150-300"
    rules: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    name: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    location: str = ""
    availability: str = ""
    education: list[Education] = Field(default_factory=list)
    links: Links
    cv: CV
    answers: dict[str, str] = Field(default_factory=dict)
    preferences: Preferences = Field(default_factory=Preferences)
    writer: WriterConfig = Field(default_factory=WriterConfig)
    submission: SubmissionConfig = Field(default_factory=SubmissionConfig)
    style: StyleConfig = Field(default_factory=StyleConfig)


_REQUIRED_PATHS = (
    ("name", ("name",)),
    ("headline", ("headline",)),
    ("cv", ("cv",)),
    ("cv.markdown", ("cv", "markdown")),
    ("cv.pdf", ("cv", "pdf")),
    ("links.github", ("links", "github")),
)


def _get_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def load_profile(path: Path) -> Profile:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("profile must be a YAML mapping")

    for label, key_path in _REQUIRED_PATHS:
        value = _get_path(data, key_path)
        if value in (None, ""):
            raise ValueError(f"missing required profile key: {label}")

    return Profile.model_validate(data)
