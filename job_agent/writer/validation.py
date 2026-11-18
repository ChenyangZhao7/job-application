from __future__ import annotations

import json
import re
from pathlib import Path

from job_agent.models import AnswerSet, JobDetail
from job_agent.profile import Profile

BANNED_PHRASES = (
    "赋能",
    "闭环",
    "生态",
    "正是我想体验的",
    "让数据说话",
    "如果有机会",
)

# Tech terms that are allowed even though they are capitalized.
ALLOWED_TERMS = {
    "Agent",
    "AI",
    "CoreBall",
    "MCP",
    "LLM",
    "Python",
    "React",
    "FastAPI",
    "API",
    "OS",
    "RAG",
    "Benchmark",
    "CLI",
    "GitHub",
}

EN_STOPWORDS = {
    "The",
    "This",
    "That",
    "These",
    "Those",
    "My",
    "Our",
    "Your",
    "Their",
    "A",
    "An",
    "And",
    "But",
    "Or",
    "If",
    "When",
    "While",
    "After",
    "Before",
    "Because",
    "So",
    "We",
    "I",
    "It",
    "In",
    "On",
    "At",
    "For",
    "To",
    "From",
    "With",
    "Without",
    "As",
    "By",
    "Of",
    "Is",
    "Are",
    "Was",
    "Were",
    "Be",
    "Been",
    "Being",
    "Have",
    "Has",
    "Had",
    "Do",
    "Does",
    "Did",
    "Can",
    "Could",
    "Should",
    "Would",
    "May",
    "Might",
    "Must",
    "Not",
    "No",
    "Yes",
}


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return cjk / len(text)


def detect_language(detail: JobDetail | None, profile: Profile, text: str = "") -> str:
    if profile.style.language in {"zh", "en"}:
        return profile.style.language
    if detail is not None:
        source = f"{detail.job.title} {detail.job.description} {detail.requirements}"
        if _cjk_ratio(source) > 0.1:
            return "zh"
        if source.strip():
            return "en"
    return "zh" if _cjk_ratio(text) > 0.3 else "en"


def _length_range(profile: Profile) -> tuple[int, int]:
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", profile.style.length or "")
    if not match:
        return 150, 300
    return int(match.group(1)), int(match.group(2))


def load_memory(path: Path | str) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    return text.strip()[:6000]


def validate_answer(
    answer: AnswerSet,
    profile: Profile,
    language: str = "auto",
    memory: str = "",
) -> list[str]:
    reasons: list[str] = []
    message = answer.message.strip()
    if not message:
        return ["empty message"]

    expected = language
    if expected == "auto":
        expected = "zh" if _cjk_ratio(message) > 0.3 else "en"

    min_len, max_len = _length_range(profile)
    length = len(message)
    words = len(re.findall(r"\b\w+\b", message))

    if expected == "zh":
        if not min_len <= length <= max_len:
            reasons.append(f"length: {length} not in {min_len}-{max_len}")
        if _cjk_ratio(message) < 0.3:
            reasons.append("language: expected Chinese")
    elif expected == "en":
        min_words = max(40, min_len // 2)
        max_words = max(120, max_len // 2)
        if not min_words <= words <= max_words:
            reasons.append(f"length: {words} words not in {min_words}-{max_words}")
        if _cjk_ratio(message) > 0.1:
            reasons.append("language: expected English")

    for phrase in BANNED_PHRASES:
        if phrase in message:
            reasons.append(f"banned phrase: {phrase}")

    sources = f"{profile.model_dump_json()}\n{memory}"
    tokens = re.findall(r"\b[A-Z][A-Za-z0-9\-]{2,}\b", message)
    for token in tokens:
        if token in ALLOWED_TERMS or token in EN_STOPWORDS or token in sources:
            continue
        reasons.append(f"grounding: unsupported claim {token}")
        break

    for number in re.findall(r"\b\d+(?:\.\d+)?\b", message):
        if number not in sources:
            reasons.append(f"grounding: unsupported number {number}")
            break

    return reasons


def parse_writer_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None
