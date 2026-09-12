import logging
from pathlib import Path

import pytest

from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.install import find_mod_file, install_module
from mtmaya_cli.module.scaffold import create_module

_MODULE_SUBDIRS = ("scripts", "plug-ins", "icons", "presets")


def _assert_copied_tree(dest_root: Path, dest_mod: Path) -> None:
    assert dest_root.is_dir()
    assert dest_mod.is_file()
    for name in _MODULE_SUBDIRS:
        assert (dest_root / name).is_dir()
    assert list(dest_root.glob("*.mod")) == []
    fields = dest_mod.read_text(encoding="utf-8").strip().split()
    assert fields[-1] == dest_root.name
    assert not Path(fields[-1]).is_absolute()


def test_install_copies_tree_with_relative_mod(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path)
    target = tmp_path / "mods"
    result = install_module(root, target=target)
    assert result.written
    dest_mod = target / "demo.mod"
    dest_root = target / "demo"
    assert result.path == dest_mod
    assert result.root == dest_root
    _assert_copied_tree(dest_root, dest_mod)
    assert dest_root != root
    assert dest_mod.read_text(encoding="utf-8").strip().endswith(" demo")


def test_install_logs_info(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = create_module("demo", directory=tmp_path)
    with caplog.at_level(logging.INFO, logger="mtmaya_cli"):
        install_module(root, target=tmp_path / "mods")
    assert "Installing module" in caplog.text
    assert "demo" in caplog.text


def test_dry_run_logs_debug(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = create_module("demo", directory=tmp_path)
    with caplog.at_level(logging.DEBUG, logger="mtmaya_cli"):
        install_module(root, target=tmp_path / "mods", dry_run=True)
    assert "Dry run" in caplog.text


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path)
    target = tmp_path / "mods"
    result = install_module(root, target=target, dry_run=True)
    assert not result.written
    assert not (target / "demo.mod").exists()
    assert not (target / "demo").exists()
    assert not target.exists()
    fields = result.contents.strip().split()
    assert fields[-1] == "demo"
    assert not Path(fields[-1]).is_absolute()


def test_install_refuses_overwrite(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path)
    target = tmp_path / "mods"
    install_module(root, target=target)
    with pytest.raises(ModuleError, match="already exists"):
        install_module(root, target=target)


def test_install_force(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path, version="0.1.0")
    target = tmp_path / "mods"
    install_module(root, target=target)
    create_module("demo", directory=tmp_path, version="9.9.9", force=True)
    result = install_module(root, target=target, force=True)
    assert " 9.9.9 " in result.contents
    dest_mod = target / "demo.mod"
    assert " 9.9.9 " in dest_mod.read_text(encoding="utf-8")
    _assert_copied_tree(target / "demo", dest_mod)


def test_install_copies_plugin_and_user_setup(tmp_path: Path) -> None:
    root = create_module(
        "demo",
        directory=tmp_path,
        with_plugin=True,
        with_user_setup=True,
    )
    target = tmp_path / "mods"
    result = install_module(root, target=target)
    dest_root = result.root
    assert (dest_root / "plug-ins" / "demo.py").is_file()
    assert (dest_root / "scripts" / "userSetup.py").is_file()
    _assert_copied_tree(dest_root, result.path)


def test_find_mod_file_prefers_matching_name(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir()
    (root / "other.mod").write_text("+ MAYAVERSION:2027 PLATFORM:mac other 0.1.0 .\n")
    matching = root / "demo.mod"
    matching.write_text("+ MAYAVERSION:2027 PLATFORM:mac demo 0.1.0 .\n")
    assert find_mod_file(root) == matching


def test_install_default_dest_uses_mod_maya_version(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path, maya_version="2028")
    env = {"MAYA_APP_DIR": str(tmp_path / "app")}
    result = install_module(root, environ=env, dry_run=True)
    assert not result.written
    assert result.path == tmp_path / "app" / "2028" / "modules" / "demo.mod"
    assert result.root == tmp_path / "app" / "2028" / "modules" / "demo"


def test_install_maya_version_overrides_dest(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path, maya_version="2028")
    env = {"MAYA_APP_DIR": str(tmp_path / "app")}
    result = install_module(root, maya_version="2029", environ=env, dry_run=True)
    assert result.path == tmp_path / "app" / "2029" / "modules" / "demo.mod"
    assert result.root == tmp_path / "app" / "2029" / "modules" / "demo"
    assert "MAYAVERSION:2029" in result.contents
    source = (root / "demo.mod").read_text(encoding="utf-8")
    assert "MAYAVERSION:2028" in source


def test_install_writes_maya_version_override_into_dest_mod(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path, maya_version="2027")
    target = tmp_path / "mods"
    result = install_module(root, target=target, maya_version="2029")
    dest_text = result.path.read_text(encoding="utf-8")
    assert "MAYAVERSION:2029" in dest_text
    source = (root / "demo.mod").read_text(encoding="utf-8")
    assert "MAYAVERSION:2027" in source


def test_install_skips_junk_names(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path)
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_text("x\n", encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "pyvenv.cfg").write_text("x\n", encoding="utf-8")
    (root / ".DS_Store").write_text("x\n", encoding="utf-8")
    (root / ".pytest_cache").mkdir()
    (root / "scripts" / "__pycache__").mkdir()
    (root / "scripts" / "__pycache__" / "y.pyc").write_text("x\n", encoding="utf-8")
    (root / "scripts" / "keep.py").write_text("ok\n", encoding="utf-8")
    target = tmp_path / "mods"
    dest = install_module(root, target=target).root
    assert not (dest / ".git").exists()
    assert not (dest / "__pycache__").exists()
    assert not (dest / ".venv").exists()
    assert not (dest / ".DS_Store").exists()
    assert not (dest / ".pytest_cache").exists()
    assert not (dest / "scripts" / "__pycache__").exists()
    assert (dest / "scripts" / "keep.py").is_file()


def test_install_io_error_is_module_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = create_module("demo", directory=tmp_path)
    target = tmp_path / "mods"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("mtmaya_cli.module.install.shutil.copytree", boom)
    with pytest.raises(ModuleError, match="disk full"):
        install_module(root, target=target)


def test_install_writes_versioned_copy(tmp_path: Path) -> None:
    root = create_module("demo", directory=tmp_path)
    env = {"MAYA_APP_DIR": str(tmp_path / "app")}
    result = install_module(root, environ=env)
    assert result.written
    dest_mod = tmp_path / "app" / "2027" / "modules" / "demo.mod"
    dest_root = tmp_path / "app" / "2027" / "modules" / "demo"
    assert result.path == dest_mod
    assert result.root == dest_root
    _assert_copied_tree(dest_root, dest_mod)


def test_find_mod_file_ambiguous(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    root.mkdir()
    (root / "a.mod").write_text("+ MAYAVERSION:2027 PLATFORM:mac a 0.1.0 .\n")
    (root / "b.mod").write_text("+ MAYAVERSION:2027 PLATFORM:mac b 0.1.0 .\n")
    with pytest.raises(ModuleError, match="Multiple"):
        find_mod_file(root)
