from typer.testing import CliRunner

from mtmaya_cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Maya" in result.stdout
    assert "--verbose" in result.stdout
    assert "--debug" in result.stdout
    assert "--quiet" in result.stdout
    assert "install" in result.stdout
    assert "uninstall" in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()
