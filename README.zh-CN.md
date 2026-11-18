# job-agent

[English](README.md) | **中文**

一个本地运行的开源求职 agent：发现并筛选岗位，按你的 profile 打分，起草一段定制消息（可选地借用你 Kimi / Doubao / ChatGPT 账号里的记忆），填好表单，默认停下来等你确认，并记录每一次投递。

## 它不是什么

- 不是群发垃圾投递的机器人。
- 不解验证码，不绕过反爬。
- 不是托管的多用户服务。

低音量使用，遵守各平台条款，保留默认的人工确认环节。

## 安装

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## 配置

```bash
cp config/profile.example.yaml config/profile.yaml
cp config/memory.example.md config/memory.md
```

用自己的资料编辑 `config/profile.yaml`。`config/profile.yaml` 和 `config/memory.md` 都在 gitignore 里，永远不要提交；仓库里只有占位示例。

API 写作后端（默认）需要设置：

```bash
# 以 DeepSeek 为例
set JOB_AGENT_LLM_BASE_URL=https://api.deepseek.com
set JOB_AGENT_LLM_API_KEY=...
```

provider 和模型在 `config/profile.yaml` 的 `writer.api` 下配置。

## 登录

```bash
python -m job_agent.cli login --platform bonjour
```

会打开一个可见的浏览器。手动登录，然后按回车。agent 不会绕过验证码；遇到时它会停下来让你处理。

## 试跑

```bash
python -m job_agent.cli run --platform bonjour --dry-run --limit 1
```

发现、打分、起草、填表各做一次，但不会提交。

## 带确认地运行

```bash
python -m job_agent.cli run --platform bonjour --limit 5
```

每份草稿都会显示岗位、分数、消息、附件，以及没答的必填问题。选 `y` 提交、`n` 跳过、`e` 编辑、`q` 退出。

## 全自动（需显式开启）

```bash
python -m job_agent.cli run --platform bonjour --yes --limit 5
```

`--yes` 必须显式写出来。它仍然遵守单次运行上限，也不会提交还留着必填问题的表单。

## 写作后端

- `api`（默认）：默认 DeepSeek，也可以选 Kimi / Doubao / OpenAI。可选的 `config/memory.md` 会注入提示词。
- `local_chat`：驱动已登录的 Kimi / Doubao / ChatGPT 网页版，用账号自己的记忆。更慢、更容易坏，需要显式开启。

```bash
python -m job_agent.cli run --platform bonjour --writer local_chat
```

## 追踪

```bash
python -m job_agent.cli status
python -m job_agent.cli status --status submitted
python -m job_agent.cli follow-ups --days 7
python -m job_agent.cli mark --platform bonjour --job-id <id> --status replied
python -m job_agent.cli resolve --platform bonjour --job-id <id> --status submitted
```

## 加一个平台适配器

新建 `job_agent/adapters/<platform>.py`，继承
`job_agent.adapters.base.PlatformAdapter`，实现：

- `login`
- `search(filters)`
- `get_job(job)`
- `open_application(job)`
- `fill(form, answers)`
- `submit(form)`
- `application_status(platform, job_id)`

主流程、匹配、写作、确认流程和追踪都与平台无关。

## 隐私

- 仓库里没有真实姓名、电话、邮箱、简历、记忆包、浏览器 profile 或 API key。
- `config/profile.yaml`、`config/memory.md`、`data/`、`.browser/`、`*.pdf` 都在 gitignore 里。
- API key 只从环境变量读取。

## 协议

MIT
