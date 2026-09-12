from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtmaya_cli import app

runner = CliRunner()

_MODULE_SUBDIRS = ("scripts", "plug-ins", "icons", "presets")


def _assert_installed(target: Path, name: str = "demo") -> Path:
    dest_mod = target / f"{name}.mod"
    dest_root = target / name
    assert dest_mod.is_file()
    assert dest_root.is_dir()
    for subdir in _MODULE_SUBDIRS:
        assert (dest_root / subdir).is_dir()
    fields = dest_mod.read_text(encoding="utf-8").strip().split()
    assert fields[-1] == name
    assert not Path(fields[-1]).is_absolute()
    return dest_mod


def test_install_copies_tree_with_relative_mod(tmp_path: Path) -> None:
    created = runner.invoke(
        app, ["module", "new", "demo", "--directory", str(tmp_path)]
    )
    assert created.exit_code == 0, created.output
    root = tmp_path / "demo"
    target = tmp_path / "mods"
    result = runner.invoke(
        app,
        ["module", "install", str(root), "--target", str(target)],
    )
    assert result.exit_code == 0, result.output
    dest_mod = _assert_installed(target)
    assert f"Copied {target / 'demo'}" in result.stdout
    assert f"Wrote {dest_mod}" in result.stdout


def test_install_default_target_is_versioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAYA_APP_DIR", str(tmp_path / "maya_app"))
    created = runner.invoke(
        app,
        [
            "module",
            "new",
            "demo",
            "--directory",
            str(tmp_path),
            "--maya-version",
            "2028",
        ],
    )
    assert created.exit_code == 0, created.output
    result = runner.invoke(app, ["module", "install", str(tmp_path / "demo")])
    assert result.exit_code == 0, result.output
    dest_dir = tmp_path / "maya_app" / "2028" / "modules"
    dest_mod = _assert_installed(dest_dir)
    assert f"Wrote {dest_mod}" in result.stdout


def test_install_maya_version_flag_overrides_dest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAYA_APP_DIR", str(tmp_path / "maya_app"))
    created = runner.invoke(
        app, ["module", "new", "demo", "--directory", str(tmp_path)]
    )
    assert created.exit_code == 0, created.output
    result = runner.invoke(
        app,
        ["module", "install", str(tmp_path / "demo"), "--maya-version", "2029"],
    )
    assert result.exit_code == 0, result.output
    dest_mod = _assert_installed(tmp_path / "maya_app" / "2029" / "modules")
    assert "MAYAVERSION:2029" in dest_mod.read_text(encoding="utf-8")
    source = (tmp_path / "demo" / "demo.mod").read_text(encoding="utf-8")
    assert "MAYAVERSION:2027" in source


def test_install_interactive(tmp_path: Path) -> None:
    created = runner.invoke(
        app, ["module", "new", "demo", "--directory", str(tmp_path)]
    )
    assert created.exit_code == 0, created.output
    root = tmp_path / "demo"
    target = tmp_path / "mods"
    result = runner.invoke(
        app,
        ["module", "install", str(root), "--target", str(target), "--interactive"],
        input="\n\n\n\n",
    )
    assert result.exit_code == 0, result.output
    dest_mod = _assert_installed(target)
    assert f"Wrote {dest_mod}" in result.stdout


def test_install_dry_run_writes_nothing(tmp_path: Path) -> None:
    created = runner.invoke(
        app, ["module", "new", "demo", "--directory", str(tmp_path)]
    )
    assert created.exit_code == 0, created.output
    target = tmp_path / "mods"
    result = runner.invoke(
        app,
        [
            "module",
            "install",
            str(tmp_path / "demo"),
            "--target",
            str(target),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not (target / "demo.mod").exists()
    assert not (target / "demo").exists()
    assert "Would copy" in result.stdout
    assert "Would write" in result.stdout
    assert str((tmp_path / "demo").resolve()) in result.stdout
    assert result.stdout.strip().endswith(" demo")
