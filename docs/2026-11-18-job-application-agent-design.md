# Job Application Agent — Design

Date: 2026-11-18
Status: Draft for approval
Owner: [maintainer]

## 1. Intent

Build a local, reusable job-application agent that turns the manual workflow we just ran on Bonjour into a configurable tool:

1. Load the candidate profile (CV, GitHub, preferences, answers).
2. Discover and filter jobs on a platform.
3. Score each job against the profile.
4. Generate a tailored "message to the team" with the candidate's own thinking (CoreBall, open source, "it exists and is used" > "I made it").
5. Fill the application form, select CV/GitHub, answer custom questions.
6. Ask for human approval (default), then submit.
7. Track applications and follow-ups.

Switching to a new platform should require only a new adapter and config, not changes to the core.

## 2. Goals

- One command runs a full batch: `job-agent run --platform bonjour`.
- Platform-specific logic is isolated in an adapter class.
- Default human-in-the-loop: show job, generated message, attachments, and wait for `y / n / e`.
- Reuse the same profile across platforms.
- Keep a local record of every application and its status.
- Never bypass login, CAPTCHA, or platform anti-bot measures.
- Keep volume low and human-reviewed by default.

## 3. Non-goals

- Not a mass-spam bot.
- Not a CAPTCHA solver or anti-bot bypass.
- Not a full ATS/CRM.
- Not a hosted multi-user service.
- Not an auto-apply tool for platforms whose terms prohibit automation.

## 4. Anti-goals

- Applying to jobs that clearly mismatch the profile just to increase volume.
- Submitting AI-generated text without review when the form asks for a personal note.
- Duplicate applications to the same job.
- Storing API keys or CV data in git.

## 5. Constraints

- Local machine: Windows, Python 3.11+.
- Browser automation: Playwright with a persistent Chromium profile.
- Login: first login is manual; the agent pauses and opens a visible browser.
- LLM: OpenAI-compatible API, configurable (DeepSeek / Kimi / OpenAI). Keys from environment variables.
- Storage: local SQLite + JSONL logs; no cloud database.
- Compliance: the user is responsible for each platform's terms; the tool defaults to human approval and low volume.

## 6. Approaches considered

### A. OpenCode skill/agent using the in-app browser tools
Fastest to prototype, but tied to the OpenCode desktop app and its browser session. Not portable.

### B. Standalone local tool (chosen)
Python + Playwright + LLM API, with a CLI and platform adapters. Portable, testable, and the adapter boundary is clean. More work around login/session persistence.

### C. Browser extension
Natural login state in the user's real browser, but each platform needs DOM-specific extension code, and distribution/updates are more complex.

Decision: **B**.

## 7. Architecture

```
job-agent/
  pyproject.toml
  README.md
  config/
    profile.yaml
    platforms/
      bonjour.yaml
    prompts/
      writer.md
      matcher.md
  job_agent/
    __main__.py          # CLI
    cli.py
    profile.py           # load/validate profile
    models.py            # Job, JobDetail, FormField, Answer, Application
    browser.py           # Playwright session, persistent context, manual login
    adapters/
      base.py            # PlatformAdapter ABC
      bonjour.py         # reference adapter
      linkedin.py        # later
      boss.py            # later
      greenhouse.py      # later
    matcher.py           # rule-based + LLM scoring
    writer.py            # LLM message generation + cleanup
    filler.py            # generic form filling helpers
    approval.py          # CLI review flow
    tracker.py           # SQLite + JSONL
    llm.py               # OpenAI-compatible client
    logging.py
  tests/
    test_matcher.py
    test_writer.py
    test_tracker.py
    fixtures/
      bonjour_job.html
      bonjour_form.html
  data/
    job_agent.db
    screenshots/
    runs/
```

### 7.1 CLI

```
job-agent login --platform bonjour
job-agent run --platform bonjour --limit 10
job-agent run --platform bonjour --dry-run
job-agent run --platform bonjour --writer local_chat
job-agent run --platform bonjour --yes          # full-auto (explicit opt-in)
job-agent status
job-agent follow-ups
```

- `login`: open a visible browser, let the user log in, save the persistent profile.
- `run`: discover → score → generate → fill → approve → submit → track.
- `--dry-run`: fill and show, never submit.
- `--writer`: `api` (default, DeepSeek) or `local_chat` (Kimi/Doubao/ChatGPT memory).
- `--yes`: full-auto submission; explicit opt-in, still subject to `max_per_run` and rate limits.
- `status`: list applications and statuses.
- `follow-ups`: list applications older than N days without a reply.

### 7.1.1 Bonjour reference flow

The first adapter targets Bonjour (`https://bonjour.bio`):

- **Job list**: `/jobs-mapping/jobs`. Filter via 筛选 → 经验 → 实习 → 完成. Job cards link to `/jobs-mapping/jobs/<id>?src=list`.
- **Login**: `/login`; QR/phone login, manual. The agent pauses until the user is logged in.
- **Job detail**: `/jobs-mapping/jobs/<id>` includes company, role, description, tags, and a “我要投递” button.
- **Application form**: `/jobs-mapping/jobs/<id>/apply?src=list`. Typical fields:
  - `CV*`: pre-uploaded CV files (`.ap-work-item`, selected with `is-selected`).
  - `作品`: GitHub/portfolio entries.
  - `Portfolio 文件`: optional upload.
  - `给团队一段话`: textarea.
  - Custom questions: varies by job (GitHub URL, “hack a system”, skills, etc.).
- **Submit**: “申请职位” button; success page carries `result=success`.
- **External redirects**: some jobs send the user off-platform; the adapter marks `external_redirect` and the matcher can exclude them per `allow_external_redirect`.
- **Duplicate detection**: the apply page shows “修改” instead of “申请职位” when an application already exists; treat that as already applied.

Selectors are owned by `adapters/bonjour.py`; the core only sees `Job`, `ApplicationForm`, and `AnswerSet`.

### 7.2 Adapter interface

```python
class PlatformAdapter(ABC):
    name: str

    async def login(self) -> None: ...
    async def search(self, filters: JobFilters) -> list[Job]: ...
    async def get_job(self, job: Job) -> JobDetail: ...
    async def open_application(self, job: Job) -> ApplicationForm: ...
    async def fill(self, form: ApplicationForm, answers: AnswerSet) -> None: ...
    async def submit(self, form: ApplicationForm) -> SubmissionResult: ...
    async def application_status(self, app: Application) -> str: ...
```

- `Job`: id, title, company, location, tags, url, description, external_redirect (bool).
- `ApplicationForm`: fields (text/textarea/select/checkbox/file), required flags, custom questions, attachment options.
- `AnswerSet`: message, per-question answers, selected attachments.
- `SubmissionResult`: success, application_url, screenshot_path, error.

Adapters own selectors and page flow. The core never imports a platform-specific selector.

### 7.3 Profile

`config/profile.yaml`:

```yaml
# Copy to config/profile.yaml (gitignored) and fill in your own data.
name: [NAME]
headline: [HEADLINE]
location: [CITY]
availability: [AVAILABILITY]
education:
  - school: [SCHOOL]
    degree: [DEGREE]
    period: [PERIOD]
links:
  github: https://github.com/[USERNAME]
  email: [EMAIL]
  phone: "[PHONE]"
cv:
  markdown: path/to/cv.md
  pdf: path/to/cv.pdf
answers:
  # Canned answers for recurring form questions. Override per job if needed.
  availability: [AVAILABILITY]
  salary_expectation: [SALARY]
  start_date: [START_DATE]
  why_this_company: ""   # leave blank to let the writer generate
preferences:
  job_types: [internship]
  exclude_keywords: [HR, 人力资源, 人事实习, 销售, 商务拓展]
  allow_external_redirect: false
  locations: [remote, Beijing, Shanghai, Shenzhen, Guangzhou, Hangzhou]
  max_per_run: 10
writer:
  backend: api            # api | local_chat
  api:
    provider: deepseek    # deepseek | kimi | doubao | openai (user-selectable)
    base_url_env: JOB_AGENT_LLM_BASE_URL
    api_key_env: JOB_AGENT_LLM_API_KEY
    model: deepseek-chat
  local_chat:
    provider: kimi        # kimi | doubao | chatgpt (use your most-used one)
    use_account_memory: true
    fresh_conversation_per_job: true
  memory_profile: config/memory.md   # optional; used by API backend
  max_chars: 300
submission:
  require_approval: true  # default: always pause before submit
  allow_full_auto: true   # user can override with --yes / config
style:
  language: auto          # auto | zh | en
  length: 150-300
  rules:
    - 不罗列简历项目；简历里有的不重复
    - 高概念、描绘蓝图
    - 结合 CoreBall：开源、被真正使用；"它存在、有人用" > "这是我做的"
    - 不写口号、排比、"赋能/闭环/生态"
    - 少用套话："正是我想体验的""让数据说话""如果有机会"
```

The profile is the single source of truth for all platforms.

### 7.4 Matching

Two-stage:

1. **Rules** (fast, deterministic):
   - job type must be internship;
   - exclude HR/recruiting roles;
   - exclude external redirects if `allow_external_redirect: false`;
   - location/remote preference;
   - keyword score against skills/projects.

2. **LLM score** (optional, for borderline jobs):
   - input: compact job detail + profile summary;
   - output: `{score: 0-100, reasons: [...], red_flags: [...]}`;
   - only jobs above `min_score` proceed.

Default `min_score: 60`; the user can review the shortlist before filling.

### 7.5 Writer

The writer is the part that benefits most from a **memory-rich LLM**. The same platform adapter and form filler should be able to use different writer backends.

#### Backends

| Backend | How it works | When to use |
|---|---|---|
| `api` | OpenAI-compatible API (DeepSeek by default; Kimi/Moonshot, Doubao/Volcengine, OpenAI also supported). The agent injects an optional curated `memory.md` into the prompt. | Default: cheap, reliable, scriptable |
| `local_chat` | Playwright drives the logged-in Kimi / Doubao / ChatGPT web UI, sends the prompt, reads the answer. Uses the account's own memory, which is usually the best personalization. | When the user wants the highest-quality, memory-aware message |

Config:

```yaml
writer:
  backend: api            # api | local_chat
  api:
    provider: deepseek    # user-selectable; DeepSeek is the cheap default
    model: deepseek-chat
  local_chat:
    provider: kimi        # user picks their most-used LLM: kimi | doubao | chatgpt
    use_account_memory: true
    fresh_conversation_per_job: true
  memory_profile: config/memory.md   # optional; used by API backend
  max_chars: 300
```

- **API backends do not expose the consumer product's memory.** `config/memory.md` is an optional, editable pack of the user's long-term themes, injected into API prompts. If it is absent, API messages are still valid but less personal.
- **`local_chat`** uses the account's own memory. The user should pick the LLM they use most (Kimi, Doubao, or ChatGPT). The agent opens a fresh conversation per job so job A's context does not bleed into job B. It requires a manual login, runs at low volume, and never bypasses CAPTCHA. Consumer UIs change often and may restrict automation, so this backend is opt-in.
- The writer output is always validated and shown in the approval step, regardless of backend.

#### Memory pack

`config/memory.md` is a living document, not a hidden model state. It should include:

- CoreBall: physical AI companion, personality/memory in the ball, multi-carrier, open source.
- The philosophy: "it exists and is used" > "I made it"; build in public; demo as ticket.
- AI companion / memory / long-term relationship themes.
- Preferred tone: first person, concrete, no slogans, no CV listing.
- Banned phrases: "赋能", "闭环", "生态", "正是我想体验的", "让数据说话", "如果有机会".

The pack is versioned and reviewed by the user; no personal data beyond what the user chooses.

#### Generation contract

- Prompt template in `config/prompts/writer.md`.
- Input: job title, company, job description, company description, profile summary, memory pack, style rules.
- Output: JSON `{message: str, answers: {question_id: str}}`.
- Cleanup: strip headings, explanations, markdown fences; enforce length; reject if it lists CV projects or uses banned phrases.
- Retry once with a stricter prompt if validation fails.
- The human approval step shows the generated text and allows editing.

### 7.6 Filler

Generic helpers:

- `fill_text(field, value)`
- `select_option(field, value)`
- `set_checkbox(field, checked)`
- `upload_file(field, path)`
- `answer_custom_question(field, answer)`

The adapter maps `FormField` to actual DOM selectors. For React-controlled inputs, use native setters + input/change events (as we did manually).

### 7.7 Approval

Default flow:

```
Job: Company — Title (location)
Score: 82
Message:
  ...
Attachments: CV ✅  GitHub ✅
Custom questions: 2 answered
[y] submit  [n] skip  [e] edit message  [q] quit
```

- **Default: always pause before submitting.**
- `--yes` (or `submission.allow_full_auto: true` plus `--yes`) enables full-auto submission. It still logs a screenshot and the submitted text, and it is opt-in per run.
- The approval step is deliberately boring and fast.

### 7.8 Tracker

SQLite tables:

- `applications(id, platform, job_id, company, title, url, score, message, status, submitted_at, last_checked_at, notes)`
- `events(id, application_id, type, payload, created_at)`

Statuses: `discovered`, `scored`, `drafted`, `approved`, `submitted`, `viewed`, `replied`, `interview`, `rejected`, `closed`.

Dedupe by `(platform, job_id)`.

### 7.9 Browser and login

- Playwright `launch_persistent_context(user_data_dir=".browser/<platform>")`.
- Visible browser by default; headless only for read-only discovery after login.
- On login/CAPTCHA: pause, screenshot, print instructions, wait for the user to press Enter.
- Never solve or bypass CAPTCHA.
- Rate limit: 3–8 seconds between actions, configurable; max 10 applications per run.

### 7.10 LLM client

- OpenAI-compatible endpoint; config via env:
  - `JOB_AGENT_LLM_BASE_URL`
  - `JOB_AGENT_LLM_API_KEY`
  - `JOB_AGENT_LLM_MODEL`
- Default: DeepSeek (cheap, good Chinese).
- Timeout, retry, and JSON parsing with a fallback.
- Redact phone/email from prompts unless needed.

## 8. Error handling

- Selector not found: screenshot + HTML snapshot; mark `adapter_error`; continue to next job.
- Login expired: pause and ask for manual login.
- CAPTCHA: pause; never bypass.
- Submit ambiguous (timeout after click): check for success text, then mark `unknown`; do not retry automatically.
- Duplicate: skip if `(platform, job_id)` already submitted.
- LLM failure: fall back to a template and require manual editing.

## 9. MVP

Ship in this order:

1. Profile loader + models + SQLite tracker.
2. Playwright session + manual login.
3. Bonjour adapter: search, job detail, application form, fill, submit.
4. API writer: DeepSeek by default, user-selectable provider, optional `memory.md`, style + grounding validation.
5. Local-chat writer: Kimi as the reference provider, using the account's own memory; fresh conversation per job.
6. Approval CLI: pause before submit by default; `--yes` full-auto is opt-in.
7. Dry-run and run reports.
8. Tests for matcher, writer cleanup, tracker dedupe.
9. A mock HTML form test for the filler (no real platform in CI).
10. Open-source hygiene: `profile.example.yaml`, `memory.example.md`, `.gitignore` for real profile/memory/data/browser profiles; no personal data in the repo.

Out of scope for MVP: LinkedIn, Boss直聘, Doubao/ChatGPT local-chat adapters, auto status checking, web UI, multi-user.

## 10. Roadmap

- v0.2: generic Greenhouse/Lever adapter (company career pages).
- v0.3: LinkedIn Easy Apply adapter (manual login, low volume).
- v0.4: Boss直聘 adapter (manual login; expect anti-bot friction).
- v0.5: optional browser writer backend (Kimi / Doubao / ChatGPT web UI, manual login).
- v0.6: local web UI for review/approval.
- v0.7: follow-up drafts and reply tracking.

## 11. Testing

- Unit: matcher rules, writer cleanup/validation, tracker dedupe, profile validation.
- Fixture: saved Bonjour job/form HTML; test the adapter's parsing and fill mapping without network.
- Manual: one dry-run on Bonjour with `--dry-run`, one approved submission.
- Never run automated submissions against a real platform in CI.

## 12. Risks

- **Terms of service**: automation may violate platform rules. Default to human approval, low volume, and no CAPTCHA bypass. The user decides which platforms are acceptable.
- **DOM drift**: adapters need maintenance; fixtures and screenshots help.
- **LLM quality**: the approval gate is the safety net; the writer validates against style rules.
- **Consumer UI automation**: driving Kimi / Doubao / ChatGPT web UIs is brittle and may conflict with their terms. The browser writer is opt-in, low-volume, and requires manual login; the API + `memory.md` path is the default.
- **PII**: local-only storage; redact sensitive fields in LLM prompts where possible.
- **Over-application**: `max_per_run`, match threshold, and human review prevent spam.

## 12.1 Resolved decisions

These were settled after the builder check; they are part of the design, not open questions.

- **Custom answers**: recurring answers live in `profile.answers` (availability, salary, start date, etc.). Job-specific questions are generated by the writer. An unknown required question pauses for human input; under `--yes` the job is skipped, never submitted blank.
- **Validation and fallback**:
  - Transport error → retry once; then template + manual edit.
  - JSON parse error → retry once; then template + manual edit.
  - Style validation failure → retry once with a stricter prompt; then template + manual edit.
  - Grounding failure → retry once; then template + manual edit.
  - `--yes` + invalid draft → skip the job. No unreviewed invalid draft is submitted.
  - API → `local_chat` fallback only if `writer.fallback_to_local_chat: true`. `local_chat` → API is manual, not automatic.
- **Grounding**: every factual claim about the candidate must be traceable to the profile or memory pack. A verifier checks claims; unsupported claims fail validation.
- **Memory pack**: optional for the API backend, authored by the user. A `memory sync` helper can extract from a pasted Kimi memory export; it is not automatic API access. It has frontmatter `version` + content hash, is gitignored, and is about 1500 tokens max. Each application records `writer_backend`, `provider`, and `memory_version`.
- **Local chat memory**: one fresh conversation per job; the account's memory applies; if configured, the memory pack is also included. Chat history persists in the account unless the user chooses a temporary chat; this is documented.
- **Sessions**: separate persistent browser profiles per platform and per writer provider. Writer and job browser may be open together. Login expiry pauses the run; under `--yes` the job is skipped and the run continues.
- **Provider config**: `llm.matcher` and `writer.api` each have `provider`, `base_url_env`, `api_key_env`, and `model`; the matcher may use a cheaper model than the writer. `writer.local_chat.provider` names the consumer site.
- **Language**: `style.language: auto` matches the job posting's language; `zh`/`en` override.
- **Shortlist gate**: optional `--review-shortlist`; the default is per-application approval. `--yes` skips per-application approval but still prints the shortlist.
- **Dedupe and identity**: key is `(platform, stable_job_id)` with URL normalization. Skipped jobs are recorded and not re-proposed unless `--retry-skipped`. `unknown` submissions require `job-agent resolve <id> submitted|failed`. The adapter detects “already applied” states (e.g., Bonjour’s “修改” button) when possible.
- **Statuses in MVP**: `submitted` only; `job-agent mark <id> viewed|replied|interview|rejected` for manual updates. `follow-ups` uses `submitted_at`.
- **Open source and personal data**: the repo contains no real name, phone, email, CV, memory pack, browser profile, or API key. `profile.example.yaml` and `memory.example.md` are committed; real files are gitignored. Keys come from environment variables.

## 13. What is left to the builder

- Exact Playwright selectors for Bonjour (derive from the current site).
- Exact LLM prompt wording (start from `config/prompts/writer.md`).
- CLI UX details (argument names, output formatting).
- Test fixture capture.
- Packaging (`pyproject.toml`, entry point).

## 14. Approval

This design is ready for review. After approval, the next step is a written implementation plan, then the MVP build.
