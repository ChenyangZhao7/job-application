from __future__ import annotations

import re

from job_agent.models import Job, MatchResult
from job_agent.profile import Profile

KEYWORDS = (
    "agent",
    "python",
    "memory",
    "ai",
    "fastapi",
    "react",
    "sql",
    "mcp",
    "llm",
    "benchmark",
)


def score_job(job: Job, profile: Profile) -> MatchResult:
    text = f"{job.title} {job.description} {job.location}".lower()
    reasons: list[str] = []

    for keyword in profile.preferences.exclude_keywords:
        token = keyword.strip()
        if not token:
            continue
        if token.isascii():
            if re.search(rf"\b{re.escape(token)}\b", text, re.IGNORECASE):
                return MatchResult(
                    score=0, reasons=[f"excluded keyword: {keyword}"], excluded=True
                )
        elif token.lower() in text:
            return MatchResult(
                score=0, reasons=[f"excluded keyword: {keyword}"], excluded=True
            )

    if job.external_redirect and not profile.preferences.allow_external_redirect:
        return MatchResult(score=0, reasons=["external redirect not allowed"], excluded=True)

    if "internship" in profile.preferences.job_types:
        if not any(marker in text for marker in ("实习", "intern", "internship")):
            return MatchResult(score=0, reasons=["not an internship"], excluded=True)

    preferred = [loc.lower() for loc in profile.preferences.locations]
    is_remote = "remote" in text or "远程" in text
    if preferred and not is_remote and not any(loc in text for loc in preferred):
        return MatchResult(score=0, reasons=["location not preferred"], excluded=True)

    score = 40
    profile_text = profile.model_dump_json().lower()
    for keyword in KEYWORDS:
        if (
            re.search(rf"\b{re.escape(keyword)}\b", text)
            and keyword in profile_text
        ):
            score += 8
    score = min(score, 80)

    if is_remote or any(loc in text for loc in preferred):
        score += 20

    reasons.append("internship match")
    if is_remote:
        reasons.append("remote")
    return MatchResult(score=min(score, 100), reasons=reasons, excluded=False)
