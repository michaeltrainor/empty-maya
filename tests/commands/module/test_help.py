from typer.testing import CliRunner

from mtmaya_cli import app

runner = CliRunner()


def test_module_help() -> None:
    result = runner.invoke(app, ["module", "--help"])
    assert result.exit_code == 0
    assert "new" in result.stdout
    assert "install" in result.stdout


def test_new_help() -> None:
    result = runner.invoke(app, ["module", "new", "--help"])
    assert result.exit_code == 0
    assert "with-plugin" in result.stdout
    assert "with-user-setup" in result.stdout
    assert "directory" in result.stdout
    assert "interactive" in result.stdout


def test_install_help() -> None:
    result = runner.invoke(app, ["module", "install", "--help"])
    assert result.exit_code == 0
    assert "dry-run" in result.stdout
    assert "target" in result.stdout
    assert "maya-version" in result.stdout
    assert "interactive" in result.stdout
