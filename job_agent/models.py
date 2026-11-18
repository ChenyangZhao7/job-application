from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = ""
    tags: list[str] = Field(default_factory=list)
    url: str = Field(min_length=1)
    description: str = ""
    external_redirect: bool = False


class JobDetail(BaseModel):
    job: Job
    company_description: str = ""
    requirements: str = ""


class JobFilters(BaseModel):
    job_types: list[str] = Field(default_factory=lambda: ["internship"])
    exclude_keywords: list[str] = Field(default_factory=list)
    allow_external_redirect: bool = False
    locations: list[str] = Field(default_factory=list)
    min_score: int = 60


class FormField(BaseModel):
    name: str = Field(min_length=1)
    label: str = ""
    kind: Literal["text", "textarea", "select", "checkbox", "file"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list)
    placeholder: str = ""


class ApplicationForm(BaseModel):
    job: Job | None = None
    fields: list[FormField] = Field(default_factory=list)
    attachment_names: list[str] = Field(default_factory=list)
    submit_label: str = "申请职位"
    already_applied: bool = False


class AnswerSet(BaseModel):
    message: str = ""
    answers: dict[str, str] = Field(default_factory=dict)
    attachments: list[str] = Field(default_factory=list)


class SubmissionResult(BaseModel):
    success: bool
    url: str = ""
    screenshot_path: str = ""
    error: str = ""


class ApplicationRecord(BaseModel):
    platform: str
    job_id: str
    company: str
    title: str
    url: str
    score: int = 0
    message: str = ""
    status: str = "submitted"
    submitted_at: str = ""
    last_checked_at: str = ""
    writer_backend: str = ""
    provider: str = ""
    memory_version: str = ""


class MatchResult(BaseModel):
    score: int = 0
    reasons: list[str] = Field(default_factory=list)
    excluded: bool = False
