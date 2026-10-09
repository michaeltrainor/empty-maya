from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtmaya_cli import app
from mtmaya_cli.module.paths import maya_module_platform
from mtmaya_cli.module.scaffold import MODULE_SUBDIRS

runner = CliRunner()


def _fake_install_runtime(python_dir: Path, *, spec: str | None = None) -> list[str]:
    _ = spec
    pkg = python_dir / "mtmaya"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("x\n", encoding="utf-8")
    (pkg / "tool.py").write_text("ok\n", encoding="utf-8")
    return ["uv", "pip", "install", "--target", str(python_dir), "mtmaya"]


def test_install_help() -> None:
    result = runner.invoke(app, ["install", "--help"])
    assert result.exit_code == 0
    assert "maya-version" in result.stdout
    assert "maya-app-dir" in result.stdout


def test_uninstall_help() -> None:
    result = runner.invoke(app, ["uninstall", "--help"])
    assert result.exit_code == 0
    assert "maya-version" in result.stdout
    assert "maya-app-dir" in result.stdout


def test_install_and_uninstall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    monkeypatch.setenv("MAYA_APP_DIR", str(tmp_path / "maya_app"))
    installed = runner.invoke(app, ["install"])
    assert installed.exit_code == 0, installed.output
    dest_dir = tmp_path / "maya_app" / "2027" / "modules"
    dest_root = dest_dir / "mtmaya"
    dest_mod = dest_dir / "mtmaya.mod"
    assert f"Installed {dest_root}" in installed.stdout
    assert f"Wrote {dest_mod}" in installed.stdout
    assert (dest_root / "python" / "mtmaya" / "tool.py").is_file()
    assert not (dest_root / "python" / "typer").exists()
    assert not (dest_root / "python" / "jinja2").exists()
    for name in MODULE_SUBDIRS:
        assert (dest_root / name).is_dir()
    setup = (dest_root / "scripts" / "userSetup.py").read_text(encoding="utf-8")
    assert "import mtmaya" in setup
    assert "import maya" not in setup
    text = dest_mod.read_text(encoding="utf-8")
    assert text.startswith("+ MAYAVERSION:")
    assert f"PLATFORM:{maya_module_platform()}" in text
    assert "PYTHONPATH +:= python" in text
    assert dest_root.resolve().as_posix() in text

    removed = runner.invoke(app, ["uninstall"])
    assert removed.exit_code == 0, removed.output
    assert f"Removed {dest_root}" in removed.stdout
    assert f"Removed {dest_mod}" in removed.stdout
    assert not dest_root.exists()
    assert not dest_mod.exists()


def test_install_maya_version_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    monkeypatch.setenv("MAYA_APP_DIR", str(tmp_path / "maya_app"))
    result = runner.invoke(app, ["install", "--maya-version", "2029"])
    assert result.exit_code == 0, result.output
    dest_dir = tmp_path / "maya_app" / "2029" / "modules"
    assert (dest_dir / "mtmaya" / "python" / "mtmaya" / "__init__.py").is_file()
    assert (dest_dir / "mtmaya.mod").is_file()
    assert not (tmp_path / "maya_app" / "2027").exists()


def test_install_maya_app_dir_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    monkeypatch.setenv("MAYA_APP_DIR", str(tmp_path / "ignored"))
    app_dir = tmp_path / "explicit"
    result = runner.invoke(app, ["install", "--maya-app-dir", str(app_dir)])
    assert result.exit_code == 0, result.output
    dest_root = app_dir / "2027" / "modules" / "mtmaya"
    assert dest_root.is_dir()
    assert not (tmp_path / "ignored").exists()


def test_uninstall_when_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAYA_APP_DIR", str(tmp_path / "maya_app"))
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output
    assert "not installed" in result.stdout
    modules = tmp_path / "maya_app" / "2027" / "modules"
    assert f"not installed at {modules}" in result.stdout
