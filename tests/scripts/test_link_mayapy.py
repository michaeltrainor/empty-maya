"""Tests for scripts/windows/link-mayapy.ps1. They do not launch Maya."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="link-mayapy.ps1 is the Windows setup script",
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "windows" / "link-mayapy.ps1"


def _run(maya_location: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MAYA_LOCATION"] = str(maya_location)
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _bin(root: Path) -> Path:
    path = root / "bin"
    path.mkdir()
    return path


def test_help_prints_usage(tmp_path: Path) -> None:
    result = _run(tmp_path, "--help")
    assert result.returncode == 0
    assert "Usage: link-mayapy.ps1" in result.stdout
    assert result.stderr == ""


def test_rejects_a_version_that_is_not_a_maya_year(tmp_path: Path) -> None:
    result = _run(tmp_path, "maya")
    assert result.returncode == 2
    assert "four-digit" in result.stderr


def test_rejects_an_unknown_option(tmp_path: Path) -> None:
    result = _run(tmp_path, "--force")
    assert result.returncode == 2
    assert "unknown option" in result.stderr


def test_missing_mayapy_names_the_path(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 1
    expected = tmp_path / "bin" / "mayapy.exe"
    assert str(expected) in result.stderr


def test_dry_run_prints_the_symlink_and_does_not_create_it(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    (bindir / "mayapy.exe").write_bytes(b"")
    result = _run(tmp_path, "--dry-run")
    assert result.returncode == 0
    assert not (bindir / "python.exe").exists()
    assert "New-Item -ItemType SymbolicLink" in result.stdout
    assert f"UV_PYTHON={bindir / 'python.exe'}" in result.stdout


def test_existing_python_exe_must_already_link_to_mayapy(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    (bindir / "mayapy.exe").write_bytes(b"")
    (bindir / "python.exe").write_bytes(b"")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "not a symlink to mayapy.exe" in result.stderr


def test_creates_a_relative_symlink_and_prints_uv_python(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    mayapy = bindir / "mayapy.exe"
    mayapy.symlink_to(Path(sys.executable))
    result = _run(tmp_path, "2027")
    link = bindir / "python.exe"
    assert result.returncode == 0, result.stderr
    assert link.is_symlink()
    assert link.readlink().name == "mayapy.exe"
    assert "created" in result.stdout
    assert f"UV_PYTHON={link}" in result.stdout
    assert sys.version.split()[0] in result.stdout


def test_second_run_keeps_an_existing_mayapy_link(tmp_path: Path) -> None:
    bindir = _bin(tmp_path)
    (bindir / "mayapy.exe").symlink_to(Path(sys.executable))
    (bindir / "python.exe").symlink_to("mayapy.exe")
    result = _run(tmp_path, "--dry-run")
    assert result.returncode == 0
    assert "already links to mayapy.exe" in result.stdout
    assert "dry-run:" not in result.stdout
