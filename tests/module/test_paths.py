from pathlib import Path

import pytest

from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.paths import (
    DEFAULT_MAYA_VERSION,
    default_maya_app_dir,
    default_pointer_path,
    maya_app_dir,
    maya_module_platform,
    user_modules_dir,
)


def test_maya_app_dir_macos_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", "darwin")
    expected = Path.home() / "Library/Preferences/Autodesk/maya"
    assert default_maya_app_dir() == expected
    assert maya_app_dir(environ={}) == expected


def test_maya_app_dir_windows_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", "win32")
    assert default_maya_app_dir() == Path.home() / "Documents" / "maya"


def test_maya_app_dir_linux_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", "linux")
    assert default_maya_app_dir() == Path.home() / "maya"


def test_maya_app_dir_from_environ(tmp_path: Path) -> None:
    custom = tmp_path / "maya_prefs"
    assert maya_app_dir(environ={"MAYA_APP_DIR": str(custom)}) == custom


def test_user_modules_dir_is_versioned_macos_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", "darwin")
    path = user_modules_dir(maya_version="2027", environ={})
    expected = Path.home() / "Library/Preferences/Autodesk/maya" / "2027" / "modules"
    assert path == expected


def test_user_modules_dir_default_version(tmp_path: Path) -> None:
    env = {"MAYA_APP_DIR": str(tmp_path)}
    assert user_modules_dir(environ=env) == tmp_path / DEFAULT_MAYA_VERSION / "modules"


def test_user_modules_dir_reads_maya_app_dir(tmp_path: Path) -> None:
    env = {"MAYA_APP_DIR": str(tmp_path / "custom")}
    path = user_modules_dir(maya_version="2028", environ=env)
    assert path == tmp_path / "custom" / "2028" / "modules"


@pytest.mark.parametrize(
    ("platform", "tag"),
    [("win32", "win64"), ("darwin", "mac"), ("linux", "linux")],
)
def test_maya_module_platform(
    platform: str, tag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", platform)
    assert maya_module_platform() == tag


def test_maya_module_platform_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", "cygwin")
    with pytest.raises(ModuleError, match="Unsupported platform"):
        maya_module_platform()


def test_default_pointer_path(tmp_path: Path) -> None:
    env = {"MAYA_APP_DIR": str(tmp_path / "maya")}
    assert (
        default_pointer_path("demo", maya_version="2027", environ=env)
        == tmp_path / "maya" / "2027" / "modules" / "demo.mod"
    )
