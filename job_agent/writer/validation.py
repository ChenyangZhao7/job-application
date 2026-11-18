from __future__ import annotations

import json
import re
from pathlib import Path

from job_agent.models import AnswerSet
from job_agent.profile import Profile

BANNED_PHRASES = (
    "赋能",
    "闭环",
    "生态",
    "正是我想体验的",
    "让数据说话",
    "如果有机会",
)

PROJECT_TERMS = (
    "CoreBall",
    "MCP",
    "巨潮",
    "历史人物",
    "音乐推荐",
    "古诗词",
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


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    return cjk / len(text)


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


def validate_answer(answer: AnswerSet, profile: Profile, language: str = "auto") -> list[str]:
    reasons: list[str] = []
    message = answer.message.strip()
    length = len(message)

    if language == "zh" or (language == "auto" and _cjk_ratio(message) > 0.3):
        if not 150 <= length <= 300:
            reasons.append(f"length: {length} not in 150-300")
        if _cjk_ratio(message) < 0.3:
            reasons.append("language: expected Chinese")
    elif language == "en":
        words = len(re.findall(r"\b\w+\b", message))
        if not 80 <= words <= 200:
            reasons.append(f"length: {words} words not in 80-200")
        if _cjk_ratio(message) > 0.1:
            reasons.append("language: expected English")

    for phrase in BANNED_PHRASES:
        if phrase in message:
            reasons.append(f"banned phrase: {phrase}")

    project_hits = sum(1 for term in PROJECT_TERMS if term in message)
    if project_hits >= 3:
        reasons.append("cv listing: too many project names")

    profile_text = profile.model_dump_json()
    tokens = re.findall(r"\b[A-Z][A-Za-z0-9\-]{2,}\b", message)
    for token in tokens:
        if token not in ALLOWED_TERMS and token not in profile_text:
            reasons.append(f"grounding: unsupported claim {token}")
            break

    for number in re.findall(r"\b\d+(?:\.\d+)?\b", message):
        if number not in profile_text:
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
