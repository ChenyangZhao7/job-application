from pathlib import Path

import pytest

from job_agent.profile import load_profile


def test_load_profile_reads_minimal_yaml(tmp_path: Path):
    p = tmp_path / "profile.yaml"
    p.write_text(
        "name: Test\nheadline: Engineer\ncv:\n  markdown: cv.md\n  pdf: cv.pdf\n"
        "links:\n  github: https://github.com/test\n",
        encoding="utf-8",
    )
    profile = load_profile(p)
    assert profile.name == "Test"
    assert profile.links.github == "https://github.com/test"


def test_load_profile_rejects_missing_cv(tmp_path: Path):
    p = tmp_path / "profile.yaml"
    p.write_text("name: Test\nheadline: Engineer\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cv"):
        load_profile(p)
