# job-agent

**English** | [中文](README.zh-CN.md)

A local, open-source job-application agent. It discovers and filters jobs,
scores them against your profile, drafts a tailored message (optionally
using your Kimi / Doubao / ChatGPT account memory), fills the form, pauses
for approval by default, and tracks every application.

## What it is not

- Not a mass-spam bot.
- Not a CAPTCHA solver or anti-bot bypass.
- Not a hosted multi-user service.

Use it at low volume, respect each platform's terms, and keep the default
human approval gate.

## Install

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Configure

```bash
cp config/profile.example.yaml config/profile.yaml
cp config/memory.example.md config/memory.md
```

Edit `config/profile.yaml` with your own data. `config/profile.yaml` and
`config/memory.md` are gitignored; never commit them. The repository only
contains placeholder examples.

For the API writer (default), set:

```bash
# DeepSeek example
set JOB_AGENT_LLM_BASE_URL=https://api.deepseek.com
set JOB_AGENT_LLM_API_KEY=...
```

Provider and model are configurable in `config/profile.yaml` under
`writer.api`.

## Login

```bash
python -m job_agent.cli login --platform bonjour
```

A visible browser opens. Log in manually, then press Enter. The agent
never bypasses a CAPTCHA; it pauses and asks you to solve it.

## Dry run

```bash
python -m job_agent.cli run --platform bonjour --dry-run --limit 1
```

This discovers, scores, drafts, and fills one job, but never submits.

## Run with approval

```bash
python -m job_agent.cli run --platform bonjour --limit 5
```

Each draft shows the job, score, message, attachments, and unanswered
required questions. Choose `y` to submit, `n` to skip, `e` to edit, `q`
to quit.

## Full auto (opt-in)

```bash
python -m job_agent.cli run --platform bonjour --yes --limit 5
```

`--yes` is explicit. It still respects the per-run limit and does not
submit a form with an unanswered required question.

## Writer backends

- `api` (default): DeepSeek by default; Kimi / Doubao / OpenAI are
  user-selectable. Optional `config/memory.md` is injected.
- `local_chat`: drives the logged-in Kimi / Doubao / ChatGPT web UI and
  uses the account's own memory. Slower and more brittle; opt-in.

```bash
python -m job_agent.cli run --platform bonjour --writer local_chat
```

## Track

```bash
python -m job_agent.cli status
python -m job_agent.cli status --status submitted
python -m job_agent.cli follow-ups --days 7
python -m job_agent.cli mark --platform bonjour --job-id <id> --status replied
python -m job_agent.cli resolve --platform bonjour --job-id <id> --status submitted
```

## Add a platform adapter

Create `job_agent/adapters/<platform>.py` subclassing
`job_agent.adapters.base.PlatformAdapter` and implement:

- `login`
- `search(filters)`
- `get_job(job)`
- `open_application(job)`
- `fill(form, answers)`
- `submit(form)`
- `application_status(platform, job_id)`

The core runner, matcher, writer, approval flow, and tracker are
platform-independent.

## Privacy

- The repo contains no real name, phone, email, CV, memory pack, browser
  profile, or API key.
- `config/profile.yaml`, `config/memory.md`, `data/`, `.browser/`, and
  `*.pdf` are gitignored.
- API keys come from environment variables.

## License

MIT
