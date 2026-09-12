from pathlib import Path

import pytest

from mtmaya import __version__
from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.package import (
    install_package,
    install_runtime,
    render_package_modfile,
    runtime_requirement,
    strip_pyside,
    uninstall_package,
    uv_pip_install,
)
from mtmaya_cli.module.scaffold import MODULE_SUBDIRS


def _write_runtime_tree(python_dir: Path, *, extra: str | None = None) -> None:
    if python_dir.exists():
        python_dir.mkdir(parents=True, exist_ok=True)
    pkg = python_dir / "mtmaya"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("__version__ = '9.9.9'\n", encoding="utf-8")
    (pkg / "keep.py").write_text("ok\n", encoding="utf-8")
    if extra:
        dep = python_dir / extra
        dep.mkdir(parents=True, exist_ok=True)
        (dep / "__init__.py").write_text("dep\n", encoding="utf-8")


def _fake_install_runtime(python_dir: Path, *, spec: str | None = None) -> list[str]:
    if python_dir.exists():
        for child in python_dir.iterdir():
            if child.is_dir():
                __import__("shutil").rmtree(child)
            else:
                child.unlink()
    extra = None
    if spec and spec.startswith("fake-runtime"):
        extra = "declared_dep"
    _write_runtime_tree(python_dir, extra=extra)
    return ["uv", "pip", "install", "--target", str(python_dir), spec or "mtmaya"]


def _assert_module_tree(dest_root: Path) -> None:
    for name in MODULE_SUBDIRS:
        assert (dest_root / name).is_dir()
    setup = dest_root / "scripts" / "userSetup.py"
    assert setup.is_file()
    text = setup.read_text(encoding="utf-8")
    assert "import mtmaya" in text
    assert "import maya" not in text
    assert "mtmaya_cli" not in text
    assert not (dest_root / "mtmaya.mod").exists()
    assert not (dest_root / "plug-ins" / "mtmaya.py").exists()


def test_runtime_requirement_names_mtmaya() -> None:
    spec = runtime_requirement()
    assert "mtmaya" in spec
    assert "mtmaya-cli" not in spec
    assert "typer" not in spec
    assert "jinja2" not in spec


def test_render_package_modfile(tmp_path: Path) -> None:
    root = tmp_path / "modules" / "mtmaya"
    root.mkdir(parents=True)
    text = render_package_modfile(version="0.1.0", module_root=root)
    lines = text.splitlines()
    assert lines[0] == f"+ MAYAVERSION:2027 PLATFORM:mac mtmaya 0.1.0 {root.resolve()}"
    assert lines[1] == "PYTHONPATH +:= python"
    assert text.endswith("\n")
    assert "\n\n" not in text


def test_install_uses_uv_target_not_copytree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str] = []

    def fake(python_dir: Path, *, spec: str | None = None) -> list[str]:
        captured.append(spec or runtime_requirement())
        return _fake_install_runtime(python_dir, spec=spec)

    monkeypatch.setattr("mtmaya_cli.module.package.install_runtime", fake)
    env = {"MAYA_APP_DIR": str(tmp_path / "maya_app")}
    result = install_package(environ=env, version="1.2.3")
    dest_dir = tmp_path / "maya_app" / "2027" / "modules"
    dest_root = dest_dir / "mtmaya"
    dest_mod = dest_dir / "mtmaya.mod"
    dest_pkg = dest_root / "python" / "mtmaya"
    assert result.root == dest_root
    assert result.path == dest_mod
    assert dest_pkg.is_dir()
    assert (dest_pkg / "keep.py").is_file()
    assert not (dest_root / "python" / "typer").exists()
    assert not (dest_root / "python" / "jinja2").exists()
    _assert_module_tree(dest_root)
    text = dest_mod.read_text(encoding="utf-8")
    assert text == result.contents
    assert "PYTHONPATH +:= python" in text
    assert captured
    assert "copytree" not in captured[0]


def test_install_declared_dep_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    env = {"MAYA_APP_DIR": str(tmp_path / "maya_app")}
    result = install_package(environ=env, spec="fake-runtime==1.0.0")
    python_dir = result.root / "python"
    assert (python_dir / "mtmaya" / "__init__.py").is_file()
    assert (python_dir / "declared_dep" / "__init__.py").is_file()
    assert not (python_dir / "typer").exists()
    assert not (python_dir / "jinja2").exists()


def test_install_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    env = {"MAYA_APP_DIR": str(tmp_path / "maya_app")}
    first = install_package(environ=env, version="0.1.0")
    stale = first.root / "python" / "stale.py"
    stale.write_text("old\n", encoding="utf-8")
    second = install_package(environ=env, version="0.2.0")
    assert second.path == first.path
    assert not stale.exists()
    assert " 0.2.0 " in second.path.read_text(encoding="utf-8")
    assert (second.root / "python" / "mtmaya" / "keep.py").is_file()
    _assert_module_tree(second.root)


def test_install_maya_version_and_app_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    app_dir = tmp_path / "custom_app"
    result = install_package(maya_version="2028", app_dir=app_dir, version="0.1.0")
    dest_dir = app_dir / "2028" / "modules"
    assert result.root == dest_dir / "mtmaya"
    assert result.path == dest_dir / "mtmaya.mod"
    assert (result.root / "python" / "mtmaya" / "keep.py").is_file()


def test_install_app_dir_overrides_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    env = {"MAYA_APP_DIR": str(tmp_path / "from_env")}
    app_dir = tmp_path / "from_flag"
    result = install_package(app_dir=app_dir, environ=env, version="0.1.0")
    assert result.root == app_dir / "2027" / "modules" / "mtmaya"
    assert not (tmp_path / "from_env").exists()


def test_uninstall_removes_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    env = {"MAYA_APP_DIR": str(tmp_path / "maya_app")}
    installed = install_package(environ=env)
    other_mod = installed.path.parent / "other.mod"
    other_root = installed.path.parent / "other"
    other_mod.write_text("keep\n", encoding="utf-8")
    other_root.mkdir()
    (other_root / "x.txt").write_text("keep\n", encoding="utf-8")
    result = uninstall_package(environ=env)
    assert result.removed
    assert not installed.root.exists()
    assert not installed.path.exists()
    assert other_mod.is_file()
    assert (other_root / "x.txt").is_file()


def test_uninstall_when_missing(tmp_path: Path) -> None:
    env = {"MAYA_APP_DIR": str(tmp_path / "maya_app")}
    result = uninstall_package(environ=env)
    assert not result.removed
    assert result.root == tmp_path / "maya_app" / "2027" / "modules" / "mtmaya"
    assert not result.root.exists()
    assert not result.path.exists()


def test_uv_pip_install_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_kwargs: object) -> object:
        seen["cmd"] = list(cmd)
        target = Path(cmd[cmd.index("--target") + 1])
        _write_runtime_tree(target)

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr("mtmaya_cli.module.package.subprocess.run", fake_run)
    monkeypatch.setattr("mtmaya_cli.module.package.find_uv", lambda: "uv")
    target = tmp_path / "python"
    target.mkdir()
    cmd = uv_pip_install("mtmaya==0.1.0", target)
    assert cmd[1:3] == ["pip", "install"]
    assert "--target" in cmd
    assert cmd[cmd.index("--target") + 1] == str(target)
    assert cmd[-1] == "mtmaya==0.1.0"
    assert seen["cmd"] == cmd
    assert not any(part == "copytree" for part in cmd)


def test_uv_pip_failure_is_module_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("uv missing")

    monkeypatch.setattr("mtmaya_cli.module.package.subprocess.run", boom)
    monkeypatch.setattr("mtmaya_cli.module.package.find_uv", lambda: "uv")
    with pytest.raises(ModuleError, match="Failed to run uv pip install"):
        uv_pip_install("mtmaya==0.1.0", tmp_path / "python")


def test_strip_pyside(tmp_path: Path) -> None:
    (tmp_path / "mtmaya").mkdir()
    (tmp_path / "PySide6").mkdir()
    (tmp_path / "PySide6-6.0.0.dist-info").mkdir()
    (tmp_path / "shiboken6").mkdir()
    (tmp_path / "keep").mkdir()
    strip_pyside(tmp_path)
    assert (tmp_path / "mtmaya").is_dir()
    assert (tmp_path / "keep").is_dir()
    assert not (tmp_path / "PySide6").exists()
    assert not (tmp_path / "PySide6-6.0.0.dist-info").exists()
    assert not (tmp_path / "shiboken6").exists()


def test_install_runtime_replaces_python_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    stale = python_dir / "stale.py"
    stale.write_text("old\n", encoding="utf-8")

    def fake_uv(spec: str, target: Path, *, argv: object = None) -> list[str]:
        _ = argv
        _write_runtime_tree(target)
        return ["uv", "pip", "install", "--target", str(target), spec]

    monkeypatch.setattr("mtmaya_cli.module.package.uv_pip_install", fake_uv)
    monkeypatch.setattr(
        "mtmaya_cli.module.package.runtime_requirement", lambda: "mtmaya==0.1.0"
    )
    install_runtime(python_dir)
    assert not stale.exists()
    assert (python_dir / "mtmaya" / "__init__.py").is_file()


def test_uv_pip_install_local_mtmaya_project(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[2] / "packages" / "mtmaya"
    target = tmp_path / "python"
    uv_pip_install(str(project), target)
    assert (target / "mtmaya" / "__init__.py").is_file()
    assert not (target / "typer").exists()
    assert not (target / "jinja2").exists()
    assert not (target / "mtmaya_cli").exists()
    assert not list(target.glob("PySide6*"))


def test_install_uses_package_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mtmaya_cli.module.package.install_runtime", _fake_install_runtime
    )
    env = {"MAYA_APP_DIR": str(tmp_path / "maya_app")}
    result = install_package(environ=env)
    assert f" {__version__} " in result.contents
