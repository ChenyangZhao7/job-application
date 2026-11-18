from typer.testing import CliRunner

from job_agent.cli import app


def test_cli_help_lists_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output and "login" in result.output
