"""Tests for the Maya debug virtual environment. They do not launch Maya."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "windows" / "venv-maya.ps1"
VERIFIER = ROOT / "scripts" / "verify_maya_venv.py"

windows_only = pytest.mark.skipif(
    sys.platform != "win32",
    reason="venv-maya.ps1 is the Windows setup script",
)


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_maya_venv", VERIFIER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(
    maya_location: Path,
    *args: str,
    cwd: Path | None = None,
    uv_python: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MAYA_LOCATION"] = str(maya_location)
    env.pop("UV_PYTHON", None)
    if uv_python is not None:
        env["UV_PYTHON"] = uv_python
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd or ROOT,
    )


def _bin(root: Path) -> Path:
    path = root / "bin"
    path.mkdir()
    return path


def _link_mayapy(bindir: Path) -> None:
    mayapy = bindir / "mayapy.exe"
    mayapy.symlink_to(Path(sys.executable))
    (bindir / "python.exe").symlink_to("mayapy.exe")


def test_gitignore_lists_venv_maya() -> None:
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".venv/" in lines
    assert ".venv.maya/" in lines


def test_debug_requirements_install_debugpy_only() -> None:
    names: list[str] = []
    text = (ROOT / "scripts" / "maya-debug.txt").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.append(stripped.split("=", 1)[0].split("[", 1)[0].strip())
    assert names == ["debugpy"]
    assert "pyside" not in text.lower()


def test_debugpy_is_not_a_project_dependency() -> None:
    for relative in (
        "pyproject.toml",
        "packages/mtmaya/pyproject.toml",
        "packages/mtmaya-cli/pyproject.toml",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert "debugpy" not in text


def test_setup_scripts_use_uv_venv_and_leave_path_alone() -> None:
    for relative in (
        "scripts/windows/venv-maya.ps1",
        "scripts/macos/venv-maya.sh",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert ".venv.maya" in text
        assert "VIRTUAL_ENV" in text
        assert "--no-managed-python" in text
        assert "--no-project" in text
        assert "python -m venv" not in text
        assert "python -m pip" not in text
        assert "--system-site-packages" not in text
        assert "$env:PATH" not in text
        assert "export PATH" not in text
        assert "verify_maya_venv.py" in text
    shell = (ROOT / "scripts" / "macos" / "venv-maya.sh").read_text(encoding="utf-8")
    assert "uv venv .venv.maya" in shell
    windows = (ROOT / "scripts" / "windows" / "venv-maya.ps1").read_text(
        encoding="utf-8"
    )
    assert '"venv", ".venv.maya"' in windows


def test_inside_matches_a_child_and_rejects_a_sibling(tmp_path: Path) -> None:
    module = _load_verifier()
    parent = tmp_path / "venv"
    child = parent / "Lib" / "debugpy" / "__init__.py"
    sibling = tmp_path / "venv-other" / "debugpy" / "__init__.py"
    assert module._inside(child, parent)
    assert module._inside(parent, parent)
    assert not module._inside(sibling, parent)


@windows_only
def test_help_prints_usage(tmp_path: Path) -> None:
    result = _run(tmp_path, "--help")
    assert result.returncode == 0
    assert "Usage: venv-maya.ps1" in result.stdout
    assert result.stderr == ""


@windows_only
def test_rejects_a_version_that_is_not_a_maya_year(tmp_path: Path) -> None:
    result = _run(tmp_path, "maya")
    assert result.returncode == 2
    assert "four-digit" in result.stderr


@windows_only
def test_rejects_an_unknown_option(tmp_path: Path) -> None:
    result = _run(tmp_path, "--pip")
    assert result.returncode == 2
    assert "unknown option" in result.stderr


@windows_only
def test_missing_mayapy_names_the_path(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 1
    expected = tmp_path / "bin" / "mayapy.exe"
    assert str(expected) in result.stderr


@windows_only
def test_missing_python_exe_points_at_the_link_script(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    (bindir / "mayapy.exe").write_bytes(b"")
    existed = (ROOT / ".venv.maya").exists()
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "link-mayapy.ps1" in result.stderr
    assert (ROOT / ".venv.maya").exists() is existed


@windows_only
def test_python_exe_must_already_link_to_mayapy(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    (bindir / "mayapy.exe").write_bytes(b"")
    (bindir / "python.exe").write_bytes(b"")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "not a symlink to mayapy.exe" in result.stderr


@windows_only
def test_dry_run_prints_uv_commands_and_does_not_create_the_venv(
    tmp_path: Path,
) -> None:
    bindir = _bin(tmp_path)
    _link_mayapy(bindir)
    existed = (ROOT / ".venv.maya").exists()
    result = _run(tmp_path, "--force", "--dry-run", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (ROOT / ".venv.maya").exists() is existed
    stdout = result.stdout
    assert f"UV_PYTHON={bindir / 'python.exe'}" in stdout
    assert f"directory={ROOT}" in stdout
    assert (
        "uv venv .venv.maya --no-managed-python --no-python-downloads --no-project"
        in stdout
    )
    install = next(
        line for line in stdout.splitlines() if line.startswith("uv pip install")
    )
    venv_python = ROOT / ".venv.maya" / "Scripts" / "python.exe"
    assert str(venv_python) in install
    assert str(ROOT / "scripts" / "maya-debug.txt") in install
    assert "--no-deps" in install
    assert "--no-project" not in install
    assert str(bindir) not in install
    assert "python -m venv" not in stdout
    assert "--system-site-packages" not in stdout
    assert "PySide6" not in stdout


@windows_only
def test_rejects_a_uv_python_that_is_not_mayas(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    _link_mayapy(bindir)
    existed = (ROOT / ".venv.maya").exists()
    result = _run(tmp_path, "--dry-run", uv_python=sys.executable)
    assert result.returncode == 1
    assert "UV_PYTHON" in result.stderr
    assert (ROOT / ".venv.maya").exists() is existed


@windows_only
def test_accepts_uv_python_when_it_is_mayas_python(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    _link_mayapy(bindir)
    python_link = bindir / "python.exe"
    existed = (ROOT / ".venv.maya").exists()
    result = _run(tmp_path, "--force", "--dry-run", uv_python=str(python_link))
    assert result.returncode == 0, result.stderr
    assert (ROOT / ".venv.maya").exists() is existed
    assert f"UV_PYTHON={python_link}" in result.stdout


@windows_only
def test_refuses_to_replace_venv_maya_without_force(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    _link_mayapy(bindir)
    venv = ROOT / ".venv.maya"
    if venv.exists():
        pytest.skip(".venv.maya already exists")
    venv.mkdir()
    marker = venv / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    try:
        result = _run(tmp_path)
        assert result.returncode == 1
        assert "already exists" in result.stderr
        assert marker.read_text(encoding="utf-8") == "keep"
    finally:
        marker.unlink(missing_ok=True)
        venv.rmdir()


@windows_only
def test_force_dry_run_does_not_delete_an_existing_venv(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    _link_mayapy(bindir)
    venv = ROOT / ".venv.maya"
    if venv.exists():
        pytest.skip(".venv.maya already exists")
    venv.mkdir()
    marker = venv / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    try:
        result = _run(tmp_path, "--force", "--dry-run")
        assert result.returncode == 0, result.stderr
        assert f"dry-run: replace {venv}" in result.stdout
        assert marker.read_text(encoding="utf-8") == "keep"
    finally:
        marker.unlink(missing_ok=True)
        venv.rmdir()
