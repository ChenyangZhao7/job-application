# Job Application Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, open-source job-application agent that discovers and filters jobs, generates memory-aware application messages, fills forms, pauses for human approval by default, and tracks every application.

**Architecture:** A Python CLI with a Playwright browser layer, a platform-adapter boundary, two writer backends (`api` with DeepSeek by default; `local_chat` driving the user's Kimi/Doubao/ChatGPT account memory), a two-stage matcher, a SQLite tracker, and a default human-approval gate. Platform-specific selectors live only in `adapters/`.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, PyYAML, Playwright, OpenAI Python SDK (OpenAI-compatible), SQLite, pytest, pytest-asyncio, Rich.

**Spec:** `docs/2026-11-18-job-application-agent-design.md`

## Global Constraints

- The project lives in `job-agent/`; run `git init` there before Task 1 if it is not already a repo.
- Python 3.11+; Windows development, cross-platform code.
- No real name, phone, email, CV, memory pack, browser profile, or API key in the repo. Real files are gitignored; only `*.example.*` files are committed.
- Default submission behavior is **pause for human approval**. Full-auto submission requires `--yes` (explicit opt-in).
- Never solve or bypass CAPTCHA; pause and ask the user to act.
- Default API writer provider: `deepseek`; provider is user-selectable.
- Default local-chat writer provider: `kimi`; the user may choose `doubao` or `chatgpt`.
- Max 10 applications per run; 3–8 second delay between browser actions; configurable.
- `style.language: auto` matches the job posting language (`zh`/`en` override).
- All generated text must pass style and grounding validation before approval.
- No automated submissions against a real platform in CI.

## Review Focus

These are the failure modes most likely to bite a real user; each has a test in the owning task.

1. **Broken login or CAPTCHA mid-run** — the run must pause with a screenshot and instructions, not spin or skip silently. (Task 3)
2. **Already-applied / duplicate job** — a job already submitted (Bonjour shows “修改”) must not be submitted twice. (Tasks 4, 9)
3. **Unknown required custom question** — the agent must pause for human input; under `--yes` it skips the job, never submits blank. (Task 5, Task 9)
4. **Invalid or hallucinated writer output** — invalid JSON, banned phrases, unsupported factual claims, or wrong language must fail validation and never reach submission. (Task 6)
5. **External-redirect job** — a job whose application leaves the platform must be excluded when `allow_external_redirect: false`. (Task 8)

---

### Task 1: Project scaffold, models, profile loader

**Files:**
- Create: `pyproject.toml`
- Create: `job_agent/__init__.py`
- Create: `job_agent/models.py`
- Create: `job_agent/profile.py`
- Create: `config/profile.example.yaml`
- Create: `config/memory.example.md`
- Test: `tests/test_profile.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Job`, `JobDetail`, `JobFilters`, `FormField`, `ApplicationForm` (including `already_applied: bool`), `AnswerSet`, `SubmissionResult`, `ApplicationRecord` (Pydantic v2 models in `job_agent/models.py`).
  - `Profile` (Pydantic model) and `load_profile(path: Path) -> Profile` in `job_agent/profile.py`.
  - `Job.id: str`, `Job.platform: str`, `Job.url: str`, `Job.external_redirect: bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_profile.py
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
```

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError
from job_agent.models import Job

def test_job_requires_id_and_url():
    job = Job(id="j1", platform="bonjour", title="T", company="C",
              location="Remote", url="https://example.com/j1")
    assert job.external_redirect is False

def test_job_rejects_empty_id():
    with pytest.raises(ValidationError):
        Job(id="", platform="bonjour", title="T", company="C",
            location="Remote", url="https://example.com/j1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_profile.py tests/test_models.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'job_agent'`.

- [ ] **Step 3: Implement the scaffold and models**

Create `pyproject.toml` with `[project]` name `job-agent`, requires-python `>=3.11`, dependencies `typer`, `pydantic>=2`, `pyyaml`, `playwright`, `openai`, `beautifulsoup4`, `rich`; dev dependencies `pytest`, `pytest-asyncio`. Add `[project.scripts] job-agent = "job_agent.cli:app"`.

In `models.py`, define Pydantic models with the fields from the spec:
`Job(id, platform, title, company, location, tags, url, description, external_redirect)`,
`JobDetail(job, company_description, requirements)`,
`FormField(name, label, kind, required, options, placeholder)`,
`ApplicationForm(job, fields, attachment_names, submit_label)`,
`AnswerSet(message, answers, attachments)`,
`SubmissionResult(success, url, screenshot_path, error)`,
`ApplicationRecord(platform, job_id, company, title, url, score, message, status, submitted_at, writer_backend, provider, memory_version)`.
Use `Field(min_length=1)` for `Job.id`, `Job.url`, `Job.title`, `Job.company`.

In `profile.py`, implement `load_profile` reading YAML and validating required `name`, `headline`, `cv.markdown`, `cv.pdf`, `links.github`; raise `ValueError` naming the missing key. Add `answers: dict[str, str] = {}`, `preferences`, `writer`, `submission`, `style` with the defaults from the design.

Create `config/profile.example.yaml` with placeholder values only; create `config/memory.example.md` with the CoreBall theme examples and a `version: 1` frontmatter.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_profile.py tests/test_models.py -v`  
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml job_agent config tests
git commit -m "feat: scaffold job agent, models, and profile loader"
```

---

### Task 2: SQLite tracker with dedupe and statuses

**Files:**
- Create: `job_agent/tracker.py`
- Test: `tests/test_tracker.py`

**Interfaces:**
- Consumes: `ApplicationRecord` from `job_agent.models`.
- Produces:
  - `Tracker(db_path: Path)` with `init()`, `record(record: ApplicationRecord) -> None`, `exists(platform: str, job_id: str) -> bool`, `mark(platform: str, job_id: str, status: str) -> None`, `list(status: str | None = None) -> list[ApplicationRecord]`, `follow_ups(days: int) -> list[ApplicationRecord]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tracker.py
from datetime import datetime, timedelta, timezone
from pathlib import Path
from job_agent.models import ApplicationRecord
from job_agent.tracker import Tracker

def make_record(job_id="j1", status="submitted"):
    return ApplicationRecord(
        platform="bonjour", job_id=job_id, company="C", title="T",
        url=f"https://example.com/{job_id}", score=80, message="hi",
        status=status, submitted_at=datetime.now(timezone.utc).isoformat(),
        writer_backend="api", provider="deepseek", memory_version="1",
    )

def test_record_and_exists(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    assert t.exists("bonjour", "j1") is False
    t.record(make_record())
    assert t.exists("bonjour", "j1") is True

def test_duplicate_record_is_ignored(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    t.record(make_record())
    t.record(make_record())
    assert len(t.list()) == 1

def test_mark_and_follow_ups(tmp_path: Path):
    t = Tracker(tmp_path / "db.sqlite")
    t.init()
    old = make_record("j2")
    old.submitted_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    t.record(old)
    t.mark("bonjour", "j2", "replied")
    assert t.list("replied")[0].job_id == "j2"
    assert [r.job_id for r in t.follow_ups(7)] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tracker.py -v`  
Expected: FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Implement `Tracker`**

Use `sqlite3` with a table:
`applications(platform TEXT, job_id TEXT, company TEXT, title TEXT, url TEXT, score INTEGER, message TEXT, status TEXT, submitted_at TEXT, last_checked_at TEXT, writer_backend TEXT, provider TEXT, memory_version TEXT, PRIMARY KEY(platform, job_id))`.
`record` uses `INSERT OR IGNORE`; `mark` updates status and `last_checked_at`; `follow_ups(days)` returns `status='submitted'` rows older than `days`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tracker.py -v`  
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/tracker.py tests/test_tracker.py
git commit -m "feat: add sqlite tracker with dedupe and statuses"
```

---

### Task 3: Playwright session and manual login pause

**Files:**
- Create: `job_agent/browser.py`
- Test: `tests/test_browser.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `BrowserSession(user_data_dir: Path, headless: bool = False)` with `start()`, `page`, `screenshot(path: Path) -> Path`, `pause_for_login(message: str) -> None`, `close()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_browser.py
from pathlib import Path
from job_agent.browser import BrowserSession

def test_session_can_render_and_screenshot(tmp_path: Path):
    s = BrowserSession(tmp_path / "profile")
    s.start()
    s.page.set_content("<html><body><h1>Login</h1></body></html>")
    out = s.screenshot(tmp_path / "shot.png")
    assert out.exists() and out.stat().st_size > 0
    s.close()

def test_pause_for_login_saves_screenshot(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    s = BrowserSession(tmp_path / "profile")
    s.start()
    s.page.set_content("<html><body>CAPTCHA</body></html>")
    s.pause_for_login("Log in, then press Enter")
    assert (tmp_path / "profile" / "login.png").exists()
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_browser.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'job_agent.browser'`.

- [ ] **Step 3: Implement `BrowserSession`**

Use `playwright.sync_api.sync_playwright().start()` and `chromium.launch_persistent_context(user_data_dir=str(user_data_dir), headless=headless)`. Create a page; `screenshot` uses `page.screenshot(path=str(path), full_page=True)`. `pause_for_login` prints the message, takes a screenshot to `user_data_dir / "login.png"`, and waits for `input()` (blocking CLI). Document that CAPTCHA is never bypassed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_browser.py -v`  
Expected: 2 passed (requires `playwright install chromium` once).

- [ ] **Step 5: Commit**

```bash
git add job_agent/browser.py tests/test_browser.py
git commit -m "feat: add playwright session with manual login pause"
```

---

### Task 4: Bonjour adapter — search, filter, job detail, dedupe

**Files:**
- Create: `job_agent/adapters/__init__.py`
- Create: `job_agent/adapters/base.py`
- Create: `job_agent/adapters/bonjour.py`
- Create: `tests/fixtures/bonjour_jobs.html`
- Test: `tests/test_bonjour_parse.py`

**Interfaces:**
- Consumes: `Job`, `JobDetail`, `BrowserSession`.
- Produces:
  - `PlatformAdapter` ABC with the methods from the spec.
  - `BonjourAdapter(session: BrowserSession)` with `search(filters) -> list[Job]`, `get_job(job) -> JobDetail`, `parse_jobs(html: str) -> list[Job]`, `is_already_applied(html: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bonjour_parse.py
from pathlib import Path
from job_agent.adapters.bonjour import BonjourAdapter

FIXTURE = Path("tests/fixtures/bonjour_jobs.html").read_text(encoding="utf-8")

def test_parse_jobs_returns_cards():
    jobs = BonjourAdapter.parse_jobs(FIXTURE)
    assert [j.title for j in jobs] == ["Intern A", "Intern B"]
    assert jobs[0].external_redirect is False
    assert jobs[1].external_redirect is True

def test_parse_jobs_skips_hr_roles():
    jobs = BonjourAdapter.parse_jobs(FIXTURE)
    assert all("HR" not in j.title for j in jobs)

def test_is_already_applied_detects_modify_button():
    assert BonjourAdapter.is_already_applied('<button>修改</button>') is True
    assert BonjourAdapter.is_already_applied('<button>申请职位</button>') is False
```

Create the fixture with two cards and an HR card: one normal card with `外部投递` marker (external redirect true), one normal, one `HR管培生` that must be skipped.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_bonjour_parse.py -v`  
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `PlatformAdapter` and `BonjourAdapter.parse_jobs`**

`base.py` defines the ABC. `bonjour.py` uses Playwright to open `https://bonjour.bio/jobs-mapping/jobs`, applies the 实习 filter (筛选 → 经验 → 实习 → 完成), scrolls to load cards, and extracts anchors matching `/jobs-mapping/jobs/`. Implement `parse_jobs` as a `@staticmethod` that uses `BeautifulSoup` (added to deps) to parse card text; `external_redirect` is true when the card contains “外部投递” or the link host is not `bonjour.bio`; skip titles containing `HR` or `人力资源`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_bonjour_parse.py -v`  
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/adapters tests/fixtures tests/test_bonjour_parse.py
git commit -m "feat: add bonjour job parsing and adapter base"
```

---

### Task 5: Bonjour adapter — application form, fill, submit, custom questions

**Files:**
- Modify: `job_agent/adapters/bonjour.py`
- Create: `tests/fixtures/bonjour_form.html`
- Test: `tests/test_bonjour_form.py`

**Interfaces:**
- Consumes: `ApplicationForm`, `FormField`, `AnswerSet`, `SubmissionResult`.
- Produces:
  - `BonjourAdapter.parse_form(html: str) -> ApplicationForm`
  - `BonjourAdapter.fill(page, form: ApplicationForm, answers: AnswerSet) -> None`
  - `BonjourAdapter.submit(page) -> SubmissionResult`
  - `BonjourAdapter.detect_unknown_required(form: ApplicationForm, answers: AnswerSet) -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bonjour_form.py
from pathlib import Path
from job_agent.adapters.bonjour import BonjourAdapter
from job_agent.models import AnswerSet

HTML = Path("tests/fixtures/bonjour_form.html").read_text(encoding="utf-8")

def test_parse_form_finds_message_and_custom_question():
    form = BonjourAdapter.parse_form(HTML)
    names = {f.name for f in form.fields}
    assert "message" in names
    assert "github" in names
    assert form.submit_label == "申请职位"

def test_unknown_required_question_is_reported():
    form = BonjourAdapter.parse_form(HTML)
    answers = AnswerSet(message="hi", answers={}, attachments=["cv"])
    assert BonjourAdapter.detect_unknown_required(form, answers) == ["github"]

def test_parse_form_detects_already_applied():
    form = BonjourAdapter.parse_form('<button>修改</button>')
    assert form.already_applied is True
```

Create the fixture with a CV item, a GitHub item, a `给团队一段话` textarea, a required `你的 GitHub*` textarea, and a `申请职位` button.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_bonjour_form.py -v`  
Expected: FAIL with `AttributeError` or `ImportError`.

- [ ] **Step 3: Implement parsing, fill, and submit**

`parse_form` extracts labels and fields; `FormField.kind` is `text`, `textarea`, `select`, `checkbox`, or `file`; `required` comes from the `*` suffix. `fill` selects CV and GitHub attachment buttons (`.ap-work-item`) by matching text, sets textareas with a native setter + `input`/`change` events, and fills custom questions from `answers.answers`. `detect_unknown_required` returns required field names not present in `answers.answers` (except `message`). `submit` clicks the button with text `申请职位`, waits for `result=success`, returns a `SubmissionResult`; if the button says `修改`, return `success=False, error="already_applied"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_bonjour_form.py -v`  
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/adapters/bonjour.py tests/fixtures/bonjour_form.html tests/test_bonjour_form.py
git commit -m "feat: add bonjour form parsing, fill, and submit"
```

---

### Task 6: API writer with memory pack, style and grounding validation

**Files:**
- Create: `job_agent/writer/__init__.py`
- Create: `job_agent/writer/api.py`
- Create: `job_agent/writer/validation.py`
- Create: `config/prompts/writer.md`
- Test: `tests/test_writer_api.py`
- Test: `tests/test_writer_validation.py`

**Interfaces:**
- Consumes: `JobDetail`, `Profile`, `AnswerSet`.
- Produces:
  - `ApiWriter(client, model: str, prompt_path: Path)` with `generate(detail, profile, memory: str, questions: list[str]) -> AnswerSet`.
  - `validate_answer(answer: AnswerSet, profile: Profile, language: str) -> list[str]` returning failure reasons.
  - `load_memory(path: Path) -> str` returning frontmatter-stripped text.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_writer_validation.py
from job_agent.models import AnswerSet, Profile
from job_agent.writer.validation import validate_answer

PROFILE = Profile(name="Test", headline="Engineer", cv={"markdown": "cv.md", "pdf": "cv.pdf"},
                  links={"github": "https://github.com/test"})

def test_banned_phrase_fails():
    a = AnswerSet(message="我想赋能这个行业，形成闭环。", answers={}, attachments=[])
    assert any("赋能" in r for r in validate_answer(a, PROFILE, "zh"))

def test_too_long_fails():
    a = AnswerSet(message="x" * 301, answers={}, attachments=[])
    assert any("length" in r for r in validate_answer(a, PROFILE, "zh"))

def test_clean_message_passes():
    a = AnswerSet(message="我想参与把 Agent 的记忆做稳。", answers={}, attachments=[])
    assert validate_answer(a, PROFILE, "zh") == []

def test_unsupported_claim_fails_grounding():
    a = AnswerSet(message="我在 Google 负责过搜索业务。", answers={}, attachments=[])
    assert any("grounding" in r for r in validate_answer(a, PROFILE, "zh"))
```

```python
# tests/test_writer_api.py
from job_agent.writer.api import parse_writer_json

def test_parse_writer_json_strips_fences():
    raw = '```json\n{"message":"hi","answers":{}}\n```'
    assert parse_writer_json(raw)["message"] == "hi"

def test_parse_writer_json_rejects_invalid():
    assert parse_writer_json("not json") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_writer_api.py tests/test_writer_validation.py -v`  
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the API writer and validation**

`ApiWriter` uses the OpenAI SDK with `base_url`/`api_key` from config. The prompt template (`config/prompts/writer.md`) includes the job, company, profile summary, memory pack, style rules, and a JSON-only instruction. `parse_writer_json` strips code fences and returns `None` on invalid JSON. `validate_answer` checks:
- length 150–300 chars (for `zh`; 80–200 words for `en`),
- banned phrases `赋能`, `闭环`, `生态`, `正是我想体验的`, `让数据说话`, `如果有机会`,
- no CV project listing (reject if it contains 3+ project names from the profile),
- grounding: every number/company/school claim appears in the profile or memory text (simple substring/entity check),
- language heuristic (`zh` has CJK ratio > 0.3; `en` has CJK ratio < 0.1).

Add `load_memory` that strips YAML frontmatter and truncates to 1500 approximate tokens.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_writer_api.py tests/test_writer_validation.py -v`  
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/writer config/prompts tests/test_writer_api.py tests/test_writer_validation.py
git commit -m "feat: add api writer with memory pack and validation"
```

---

### Task 7: Local-chat writer for Kimi (account memory)

**Files:**
- Create: `job_agent/writer/local_chat.py`
- Test: `tests/test_writer_local_chat.py`
- Test fixture: `tests/fixtures/kimi_chat.html`

**Interfaces:**
- Consumes: `JobDetail`, `Profile`, `BrowserSession`.
- Produces:
  - `LocalChatWriter(session: BrowserSession, provider: str = "kimi", fresh_conversation_per_job: bool = True)` with `generate(detail, profile, questions) -> AnswerSet`.
  - `extract_chat_answer(html: str) -> str` for testing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_writer_local_chat.py
from pathlib import Path
from job_agent.writer.local_chat import extract_chat_answer

HTML = Path("tests/fixtures/kimi_chat.html").read_text(encoding="utf-8")

def test_extract_chat_answer_ignores_prompt_and_copy_buttons():
    assert extract_chat_answer(HTML) == "这是生成的回答。"

def test_extract_chat_answer_returns_empty_when_missing():
    assert extract_chat_answer("<html></html>") == ""
```

Create the fixture with a user prompt block, a `Copy` button, and an assistant answer block containing `这是生成的回答。`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_writer_local_chat.py -v`  
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the local-chat writer**

`generate` opens a new chat (`provider == "kimi"` → `https://www.kimi.com/`), focuses `.chat-input-editor`, inserts the prompt with `document.execCommand('insertText')`, clicks `.send-button-container`, waits for generation to finish (no `Working`/`停止` text, bounded timeout), extracts the last assistant answer via `extract_chat_answer`, and returns `AnswerSet(message=answer, answers={}, attachments=[])`. The writer uses its own persistent browser profile (e.g., `.browser/kimi`), separate from the platform session. If the page shows a login modal, call `session.pause_for_login("Log in to Kimi, then press Enter")`. Fresh conversation per job; never reuse the previous conversation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_writer_local_chat.py -v`  
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/writer/local_chat.py tests/fixtures/kimi_chat.html tests/test_writer_local_chat.py
git commit -m "feat: add kimi local-chat writer"
```

---

### Task 8: Matcher — internship, HR, external redirect, location, score

**Files:**
- Create: `job_agent/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `Job`, `Profile`.
- Produces:
  - `score_job(job: Job, profile: Profile) -> MatchResult` where `MatchResult(score: int, reasons: list[str], excluded: bool)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_matcher.py
from job_agent.matcher import score_job
from job_agent.models import Job, Profile

PROFILE = Profile(
    name="Test", headline="AI Agent Engineer",
    cv={"markdown": "cv.md", "pdf": "cv.pdf"},
    links={"github": "https://github.com/test"},
    preferences={"job_types": ["internship"], "exclude_keywords": ["HR"],
                 "allow_external_redirect": False,
                 "locations": ["remote", "Beijing"]},
)

def job(**kw):
    base = dict(id="j1", platform="bonjour", title="AI Agent Intern",
                company="C", location="Remote", url="https://x/j1",
                description="Python Agent memory", external_redirect=False)
    base.update(kw)
    return Job(**base)

def test_excludes_hr():
    r = score_job(job(title="HR Intern"), PROFILE)
    assert r.excluded is True

def test_excludes_external_redirect_when_disallowed():
    r = score_job(job(external_redirect=True), PROFILE)
    assert r.excluded is True

def test_scores_matching_job_above_threshold():
    r = score_job(job(), PROFILE)
    assert r.excluded is False and r.score >= 60

def test_excludes_non_internship():
    r = score_job(job(title="Senior Engineer"), PROFILE)
    assert r.excluded is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_matcher.py -v`  
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `score_job`**

Rules in order: exclude if title/description contains an `exclude_keywords` term; exclude if `external_redirect` and not allowed; exclude if no internship marker (`实习`/`intern`) and `job_types` is `internship`; exclude if location not in preferred locations and not remote. Score = 40 base + keyword matches from skills/projects (up to 40) + location/remote bonus (20), capped at 100. Reasons are human-readable.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_matcher.py -v`  
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/matcher.py tests/test_matcher.py
git commit -m "feat: add job matcher with exclusion rules"
```

---

### Task 9: Approval CLI and run loop

**Files:**
- Create: `job_agent/approval.py`
- Create: `job_agent/cli.py`
- Create: `job_agent/runner.py`
- Test: `tests/test_runner.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces:
  - `Decision` enum: `SUBMIT`, `SKIP`, `EDIT`, `QUIT`.
  - `review(record, message, attachments, input_fn=input) -> Decision`.
  - `Runner(adapter, writer, tracker, profile, dry_run=False, auto=False, limit=10)` with `run() -> RunReport`.
  - CLI commands: `login`, `run`, `status`, `follow-ups`, `mark`, `resolve`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runner.py
from job_agent.approval import Decision
from job_agent.runner import Runner

# Define JOB (id="j1"), DETAIL, FORM, RESULT, ANSWER, profile, a fresh
# Tracker per test, and a make_record(job_id) helper at module/test level
# before the cases below.

class FakeAdapter:
    name = "fake"
    def search(self, filters): return [JOB]
    def get_job(self, job): return DETAIL
    def open_application(self, job): return FORM
    def fill(self, form, answers): self.filled = answers
    def submit(self, form): return RESULT
    def application_status(self, app): return "submitted"

class FakeWriter:
    def generate(self, *a, **k): return ANSWER

def test_runner_does_not_submit_in_dry_run():
    adapter = FakeAdapter()
    r = Runner(adapter, FakeWriter(), tracker, profile, dry_run=True)
    report = r.run()
    assert report.submitted == 0 and adapter.filled is not None

def test_runner_submits_after_approval():
    adapter = FakeAdapter()
    r = Runner(adapter, FakeWriter(), tracker, profile, auto=True)
    report = r.run()
    assert report.submitted == 1

def test_runner_skips_unknown_required_question_in_auto_mode():
    adapter = FakeAdapter()
    adapter.open_application = lambda job: FORM_WITH_UNKNOWN_REQUIRED
    r = Runner(adapter, FakeWriter(), tracker, profile, auto=True)
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1

def test_runner_skips_already_submitted_job():
    tracker.record(make_record("j1"))
    adapter = FakeAdapter()
    r = Runner(adapter, FakeWriter(), tracker, profile, auto=True)
    report = r.run()
    assert report.submitted == 0 and report.skipped == 1
```

```python
# tests/test_cli.py
from typer.testing import CliRunner
from job_agent.cli import app

def test_cli_help_lists_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output and "login" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runner.py tests/test_cli.py -v`  
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement approval, runner, and CLI**

`approval.review` prints the job, score, message, attachments, and custom-question count; reads `y/n/e/q`; `e` opens `$EDITOR` (or prints the message for editing) and re-reviews. `Runner.run` loops jobs: matcher exclusion → dedupe → writer → detect unknown required → fill → dry-run? stop : approval/auto → submit → tracker. `RunReport` has `submitted`, `skipped`, `failed`, `applications`. CLI uses Typer with the commands and options from the design (`--platform`, `--writer`, `--dry-run`, `--yes`, `--limit`, `--review-shortlist`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runner.py tests/test_cli.py -v`  
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add job_agent/approval.py job_agent/runner.py job_agent/cli.py tests/test_runner.py tests/test_cli.py
git commit -m "feat: add approval flow and run loop"
```

---

### Task 10: Open-source hygiene, docs, and mock end-to-end

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `config/profile.example.yaml` (final)
- Create: `config/memory.example.md` (final)
- Create: `tests/fixtures/mock_bonjour.html`
- Create: `tests/test_end_to_end_mock.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: all prior modules.
- Produces: runnable package and a mock E2E test.

- [ ] **Step 1: Write the failing E2E test**

```python
# tests/test_end_to_end_mock.py
from pathlib import Path
from job_agent.adapters.bonjour import BonjourAdapter
from job_agent.browser import BrowserSession
from job_agent.models import AnswerSet

HTML = Path("tests/fixtures/mock_bonjour.html").read_text(encoding="utf-8")

def test_mock_form_fill_and_submit_contract():
    form = BonjourAdapter.parse_form(HTML)
    assert "message" in {f.name for f in form.fields}
    assert BonjourAdapter.detect_unknown_required(
        form, AnswerSet(message="hi", answers={"github": "https://github.com/test"}, attachments=[])
    ) == []

def test_mock_form_fill_sets_values(tmp_path: Path):
    s = BrowserSession(tmp_path / "p")
    s.start()
    s.page.set_content(HTML)
    form = BonjourAdapter.parse_form(HTML)
    BonjourAdapter.fill(
        s.page, form,
        AnswerSet(message="hi", answers={"github": "https://github.com/test"},
                  attachments=["cv", "github"]),
    )
    assert s.page.input_value("textarea[name=message]") == "hi"
    assert s.page.input_value("textarea[name=github]") == "https://github.com/test"
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_end_to_end_mock.py -v`  
Expected: FAIL until the fixture exists.

- [ ] **Step 3: Add `.gitignore`, README, examples, and fixture**

`.gitignore` must include:
`config/profile.yaml`, `config/memory.md`, `data/`, `.browser/`, `*.pdf`, `.env`, `__pycache__/`, `.pytest_cache/`.

README covers install (`pip install -e .`, `playwright install chromium`), login, dry-run, `--writer local_chat`, full-auto warning, privacy/open-source note, and how to add a new adapter.

Examples use placeholders only. The mock form mimics the Bonjour form with CV/GitHub/message/custom GitHub question.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`  
Expected: all tests pass.

- [ ] **Step 5: Manual smoke test**

Run:
```
job-agent login --platform bonjour
job-agent run --platform bonjour --dry-run --limit 1
```
Expected: browser opens, login pauses for the user, one job is drafted and filled, and nothing is submitted.

- [ ] **Step 6: Commit**

```bash
git add .gitignore README.md config tests pyproject.toml
git commit -m "feat: add open-source hygiene, docs, and mock e2e"
```

---

## Self-Review

- **Spec coverage:** The plan covers profile, tracker, Bonjour discovery, form fill/submit, API writer + memory, local-chat writer, matcher, approval/full-auto, open-source hygiene, and tests for every Review Focus item. The design's roadmap items (LinkedIn/Boss/other consumer UIs) are intentionally out of MVP.
- **Step scan:** Each task has a failing test, a fail run, an implementation step with exact interfaces, a pass run, and a commit. No “TBD” or “handle edge cases” lines.
- **Type consistency:** `Job`, `JobDetail`, `ApplicationForm`, `AnswerSet`, `SubmissionResult`, `Tracker`, `MatchResult`, `Decision`, `Runner` are defined before use. `BonjourAdapter` methods match the ABC.
- **Review Focus:** Login/CAPTCHA (Task 3), duplicate/already applied (Tasks 4, 9), unknown required question (Tasks 5, 9), invalid/hallucinated writer output (Task 6), external redirect (Task 8).
- **Proportion:** The plan is longer than the spec because it fixes exact interfaces and tests; it does not include full implementations.
