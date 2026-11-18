from __future__ import annotations

from abc import ABC, abstractmethod

from job_agent.models import (
    AnswerSet,
    ApplicationForm,
    Job,
    JobDetail,
    JobFilters,
    SubmissionResult,
)


class PlatformAdapter(ABC):
    name: str

    def ensure_login(self) -> None:
        """Pause for manual login if the session is not authenticated."""
        return None

    def detect_unknown_required(self, form: ApplicationForm, answers: AnswerSet) -> list[str]:
        """Return required fields that have no non-empty answer."""
        return []

    @abstractmethod
    def login(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, filters: JobFilters) -> list[Job]:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job: Job) -> JobDetail:
        raise NotImplementedError

    @abstractmethod
    def open_application(self, job: Job) -> ApplicationForm:
        raise NotImplementedError

    @abstractmethod
    def fill(self, form: ApplicationForm, answers: AnswerSet) -> None:
        raise NotImplementedError

    @abstractmethod
    def submit(self, form: ApplicationForm) -> SubmissionResult:
        raise NotImplementedError

    @abstractmethod
    def application_status(self, platform: str, job_id: str) -> str:
        raise NotImplementedError
