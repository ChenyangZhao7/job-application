from __future__ import annotations

from enum import Enum
from typing import Callable


class Decision(str, Enum):
    SUBMIT = "submit"
    SKIP = "skip"
    EDIT = "edit"
    QUIT = "quit"


def review(
    job_title: str,
    company: str,
    score: int,
    message: str,
    attachments: list[str],
    unknown_questions: list[str],
    input_fn: Callable[[str], str] = input,
) -> Decision:
    print(f"\nJob: {company} — {job_title}")
    print(f"Score: {score}")
    print("Message:")
    print(message)
    print(f"Attachments: {', '.join(attachments) or 'none'}")
    if unknown_questions:
        print(f"Unanswered required questions: {', '.join(unknown_questions)}")

    while True:
        choice = input_fn("[y] submit  [n] skip  [e] edit  [q] quit: ").strip().lower()
        if choice in {"y", "yes", "submit"}:
            return Decision.SUBMIT
        if choice in {"n", "no", "skip"}:
            return Decision.SKIP
        if choice in {"e", "edit"}:
            return Decision.EDIT
        if choice in {"q", "quit"}:
            return Decision.QUIT
        print("Please choose y, n, e, or q.")
