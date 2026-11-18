from __future__ import annotations

import os
from pathlib import Path

import typer
from rich import print as rprint

from job_agent.adapters.bonjour import BonjourAdapter
from job_agent.browser import BrowserSession
from job_agent.profile import Profile, load_profile
from job_agent.runner import Runner
from job_agent.tracker import Tracker
from job_agent.writer.api import ApiWriter
from job_agent.writer.local_chat import LocalChatWriter
from job_agent.writer.validation import load_memory

app = typer.Typer(no_args_is_help=True, help="Local job application agent.")
DEFAULT_PROFILE = Path("config/profile.yaml")
DEFAULT_DB = Path("data/job_agent.db")


def _load_profile(path: Path) -> Profile:
    if not Path(path).exists():
        raise typer.BadParameter(
            f"profile not found: {path}. Copy config/profile.example.yaml first."
        )
    return load_profile(Path(path))


def _tracker() -> Tracker:
    tracker = Tracker(DEFAULT_DB)
    tracker.init()
    return tracker


def _make_writer(writer_name: str, profile: Profile, session: BrowserSession):
    if writer_name == "api":
        config = profile.writer.api
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise typer.BadParameter(
                f"missing {config.api_key_env}; set it or use --writer local_chat"
            )
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv(config.base_url_env) or None,
        )
        return ApiWriter(
            client,
            model=config.model,
            prompt_path=Path("config/prompts/writer.md"),
            max_chars=profile.writer.max_chars,
            memory=load_memory(profile.writer.memory_profile),
        )
    if writer_name == "local_chat":
        return LocalChatWriter(
            session,
            provider=profile.writer.local_chat.provider,
            fresh_conversation_per_job=profile.writer.local_chat.fresh_conversation_per_job,
        )
    raise typer.BadParameter("--writer must be api or local_chat")


@app.command()
def login(
    platform: str = typer.Option("bonjour", "--platform"),
    profile: Path = typer.Option(DEFAULT_PROFILE, "--profile"),
):
    """Open a visible browser and let the user log in."""
    _load_profile(profile)
    session = BrowserSession(Path(".browser") / platform)
    try:
        session.start()
        if platform == "bonjour":
            BonjourAdapter(session).login()
        else:
            raise typer.BadParameter(f"unsupported platform: {platform}")
    finally:
        session.close()


@app.command()
def run(
    platform: str = typer.Option("bonjour", "--platform"),
    writer: str = typer.Option("api", "--writer"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
    limit: int = typer.Option(10, "--limit"),
    profile: Path = typer.Option(DEFAULT_PROFILE, "--profile"),
):
    """Discover, score, draft, fill, approve, and submit jobs."""
    loaded = _load_profile(profile)
    session = BrowserSession(Path(".browser") / platform)
    session.start()
    try:
        if platform != "bonjour":
            raise typer.BadParameter(f"unsupported platform: {platform}")
        adapter = BonjourAdapter(session)
        writer_backend = _make_writer(writer, loaded, session)
        tracker = _tracker()
        report = Runner(
            adapter,
            writer_backend,
            tracker,
            loaded,
            dry_run=dry_run,
            auto=yes,
            limit=limit,
        ).run()
        rprint(
            f"[bold]submitted[/bold]={report.submitted} "
            f"[bold]drafted[/bold]={report.drafted} "
            f"[bold]skipped[/bold]={report.skipped} "
            f"[bold]failed[/bold]={report.failed}"
        )
    finally:
        session.close()


@app.command()
def status(
    status_filter: str = typer.Option(None, "--status"),
):
    """List tracked applications."""
    tracker = _tracker()
    for record in tracker.list(status_filter):
        rprint(f"{record.platform}  {record.company} — {record.title}  [{record.status}]")


@app.command("follow-ups")
def follow_ups(
    days: int = typer.Option(7, "--days"),
):
    """List submitted applications older than N days."""
    tracker = _tracker()
    for record in tracker.follow_ups(days):
        rprint(f"{record.platform}  {record.company} — {record.title}  {record.submitted_at}")


@app.command()
def mark(
    platform: str = typer.Option(..., "--platform"),
    job_id: str = typer.Option(..., "--job-id"),
    status_value: str = typer.Option(..., "--status"),
):
    """Manually update an application status."""
    _tracker().mark(platform, job_id, status_value)
    rprint(f"updated {platform}/{job_id} → {status_value}")


@app.command()
def resolve(
    platform: str = typer.Option(..., "--platform"),
    job_id: str = typer.Option(..., "--job-id"),
    status_value: str = typer.Option(..., "--status"),
):
    """Resolve an unknown submission."""
    _tracker().mark(platform, job_id, status_value)
    rprint(f"resolved {platform}/{job_id} → {status_value}")
