import logging
from pathlib import Path

import pytest

from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.paths import maya_module_platform
from mtmaya_cli.module.scaffold import (
    MODULE_SUBDIRS,
    create_module,
    render_user_setup,
    validate_name,
)


def test_create_module_logs_info(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="mtmaya_cli"):
        create_module("demo", directory=tmp_path)
    assert "Creating module" in caplog.text
    assert "demo" in caplog.text


def test_create_module_logs_debug_writes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="mtmaya_cli"):
        create_module("demo", directory=tmp_path, with_plugin=True)
    assert "Wrote .mod" in caplog.text
    assert "Wrote plugin stub" in caplog.text


def test_create_module_tree(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path)
    assert root == (tmp_path / "demo").resolve()
    assert (root / "demo.mod").is_file()
    for name in MODULE_SUBDIRS:
        assert (root / name).is_dir()
    assert not (root / "plug-ins" / "demo.py").exists()
    assert not (root / "scripts" / "userSetup.py").exists()
    text = (root / "demo.mod").read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert text.strip().endswith(".")
    assert f"PLATFORM:{maya_module_platform()}" in text


def test_create_module_with_plugin(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path, with_plugin=True)
    plugin = root / "plug-ins" / "demo.py"
    text = plugin.read_text(encoding="utf-8")
    assert "maya_useNewAPI = True" in text
    assert "def initializePlugin" in text
    assert "def uninitializePlugin" in text


def test_create_module_with_user_setup(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path, with_user_setup=True)
    setup = root / "scripts" / "userSetup.py"
    text = setup.read_text(encoding="utf-8")
    assert "demo" in text
    assert "import demo" not in text
    assert "maya.cmds" not in text
    assert "maya.standalone" not in text
    assert "import maya" not in text


def test_create_module_startup_import(tmp_path: Path) -> None:
    root = create_module(
        "demo",
        directory=tmp_path,
        with_user_setup=True,
        startup_import="mtmaya",
    )
    text = (root / "scripts" / "userSetup.py").read_text(encoding="utf-8")
    assert "import mtmaya" in text
    assert "import maya" not in text
    assert render_user_setup("demo", startup_import="mtmaya") == text


def test_create_module_refuses_overwrite(tmp_path: Path) -> None:
    create_module("demo", directory=tmp_path)
    with pytest.raises(ModuleError, match="already exists"):
        create_module("demo", directory=tmp_path)


def test_create_module_force(tmp_path: Path) -> None:
    create_module("demo", directory=tmp_path, version="0.1.0")
    root = create_module("demo", directory=tmp_path, version="2.0.0", force=True)
    text = (root / "demo.mod").read_text(encoding="utf-8")
    assert " 2.0.0 " in text


def test_create_module_force_removes_optional_stubs(tmp_path: Path) -> None:
    root = create_module(
        "demo",
        directory=tmp_path,
        with_plugin=True,
        with_user_setup=True,
    )
    assert (root / "plug-ins" / "demo.py").is_file()
    assert (root / "scripts" / "userSetup.py").is_file()
    create_module("demo", directory=tmp_path, force=True)
    assert not (root / "plug-ins" / "demo.py").exists()
    assert not (root / "scripts" / "userSetup.py").exists()
    assert (root / "demo.mod").is_file()


def test_create_module_io_error_is_module_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Path, *_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "mkdir", boom)
    with pytest.raises(ModuleError, match="permission denied"):
        create_module("demo", directory=tmp_path)


@pytest.mark.parametrize("name", ["has space", "foo/bar", r"foo\bar", "", ".", ".."])
def test_invalid_names(name: str) -> None:
    with pytest.raises(ModuleError):
        validate_name(name)
