"""Tests for mtmaya.development.listen. They do not launch Maya."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

from mtmaya.development import (
    DEBUG_VENV_ENV,
    DevelopmentError,
    _find_venv,
    listen,
)

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "packages" / "mtmaya" / "src" / "mtmaya"

_FAKE_DEBUGPY = """\
calls = []

def configure(**kwargs):
    calls.append(("configure", kwargs))

def listen(endpoint, *, in_process_debug_adapter=False):
    calls.append(("listen", endpoint, in_process_debug_adapter))
    host, port = endpoint
    return (host, 5678 if port == 0 else port)

def wait_for_client():
    calls.append(("wait",))
"""

_RAISING_DEBUGPY = """\
def configure(**kwargs):
    return None

def listen(endpoint, *, in_process_debug_adapter=False):
    raise RuntimeError("debugpy.listen() has already been called on this process")

def wait_for_client():
    raise AssertionError("wait_for_client should not run")
"""


def _install_debugpy(venv: Path, source: str) -> Path:
    site = venv / "Lib" / "site-packages"
    package = site / "debugpy"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(source, encoding="utf-8")
    return venv


def _clear_debugpy() -> None:
    for name in list(sys.modules):
        if name == "debugpy" or name.startswith("debugpy."):
            sys.modules.pop(name, None)


@pytest.fixture
def debugpy_modules() -> object:
    saved_path = list(sys.path)
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "debugpy" or name.startswith("debugpy.")
    }
    _clear_debugpy()
    yield
    _clear_debugpy()
    sys.modules.update(saved)
    sys.path[:] = saved_path


def test_import_mtmaya_does_not_load_development() -> None:
    import importlib

    import mtmaya

    sys.modules.pop("mtmaya.development", None)
    importlib.reload(mtmaya)
    assert "mtmaya.development" not in sys.modules
    tree = ast.parse((RUNTIME / "__init__.py").read_text(encoding="utf-8"))
    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert "mtmaya.development" not in imported
    assert "debugpy" not in imported


def test_user_setup_template_does_not_listen() -> None:
    template = (
        ROOT
        / "packages"
        / "mtmaya-cli"
        / "src"
        / "mtmaya_cli"
        / "templates"
        / "module"
        / "userSetup.py.j2"
    )
    text = template.read_text(encoding="utf-8")
    assert "debugpy" not in text
    assert "development" not in text
    assert "listen" not in text


def test_development_import_does_not_load_debugpy_or_maya() -> None:
    _clear_debugpy()
    sys.modules.pop("maya", None)
    import importlib

    import mtmaya.development as development

    importlib.reload(development)
    assert "debugpy" not in sys.modules
    assert "maya" not in sys.modules


def test_listen_loads_debugpy_from_venv_and_does_not_touch_path(
    tmp_path: Path, debugpy_modules: object
) -> None:
    _ = debugpy_modules
    venv = _install_debugpy(tmp_path / ".venv.maya", _FAKE_DEBUGPY)
    path = os.environ["PATH"]
    result = listen(venv=venv, environ={})
    assert result.host == "127.0.0.1"
    assert result.port == 5678
    assert result.venv == venv
    assert result.waiting is False
    assert os.environ["PATH"] == path
    calls = sys.modules["debugpy"].calls
    assert calls[0] == ("configure", {"subProcess": False})
    assert calls[1] == ("listen", ("127.0.0.1", 5678), True)
    assert not any(call[0] == "wait" for call in calls)
    loaded = Path(sys.modules["debugpy"].__file__)
    assert loaded.parent.parent == venv / "Lib" / "site-packages"


def test_listen_waits_when_asked(tmp_path: Path, debugpy_modules: object) -> None:
    _ = debugpy_modules
    venv = _install_debugpy(tmp_path / ".venv.maya", _FAKE_DEBUGPY)
    result = listen(venv=venv, wait=True, port=0, environ={})
    assert result.port == 5678
    assert result.waiting is True
    assert ("wait",) in sys.modules["debugpy"].calls


def test_listen_reports_an_adapter_that_is_already_running(
    tmp_path: Path, debugpy_modules: object
) -> None:
    _ = debugpy_modules
    venv = _install_debugpy(tmp_path / ".venv.maya", _RAISING_DEBUGPY)
    with pytest.raises(DevelopmentError, match="already been called"):
        listen(venv=venv, environ={})


def test_listen_rejects_a_bad_port(tmp_path: Path) -> None:
    with pytest.raises(DevelopmentError, match="65535"):
        listen(port=70000, venv=tmp_path / ".venv.maya", environ={})


def test_listen_rejects_debugpy_already_loaded_from_somewhere_else(
    tmp_path: Path, debugpy_modules: object
) -> None:
    _ = debugpy_modules
    other = tmp_path / "other" / "debugpy" / "__init__.py"
    other.parent.mkdir(parents=True)
    other.write_text("calls = []\n", encoding="utf-8")
    import types

    module = types.ModuleType("debugpy")
    module.__file__ = str(other)
    sys.modules["debugpy"] = module
    venv = _install_debugpy(tmp_path / ".venv.maya", _FAKE_DEBUGPY)
    with pytest.raises(DevelopmentError, match="already loaded"):
        listen(venv=venv, environ={})
    assert sys.modules["debugpy"] is module


def test_explicit_venv_must_contain_debugpy(tmp_path: Path) -> None:
    with pytest.raises(DevelopmentError, match="not installed"):
        listen(venv=tmp_path / ".venv.maya", environ={})


def test_refuses_a_venv_inside_maya(tmp_path: Path) -> None:
    maya = tmp_path / "Maya2027"
    (maya / "bin").mkdir(parents=True)
    (maya / "bin" / "mayapy.exe").write_bytes(b"")
    venv = _install_debugpy(maya / ".venv.maya", _FAKE_DEBUGPY)
    with pytest.raises(DevelopmentError, match="Maya's install"):
        listen(venv=venv, environ={})


def test_find_venv_walks_up_to_a_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    _install_debugpy(checkout / ".venv.maya", "x = 1\n")
    origin = checkout / "packages" / "mtmaya" / "src" / "mtmaya" / "development"
    origin.mkdir(parents=True)
    found = _find_venv(None, {}, origin=origin / "__init__.py", cwd=tmp_path / "else")
    assert found == checkout / ".venv.maya"


def test_find_venv_skips_an_empty_directory_and_an_install_copy(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    _install_debugpy(checkout / ".venv.maya", "x = 1\n")
    nested = checkout / "nested"
    (nested / ".venv.maya").mkdir(parents=True)
    maya = checkout / "Maya2027"
    (maya / "bin").mkdir(parents=True)
    (maya / "bin" / "mayapy.exe").write_bytes(b"")
    _install_debugpy(maya / ".venv.maya", "x = 1\n")
    origin = nested / "pkg" / "module.py"
    origin.parent.mkdir(parents=True)
    found = _find_venv(None, {}, origin=origin, cwd=maya)
    assert found == checkout / ".venv.maya"


def test_find_venv_prefers_an_explicit_path_over_the_environment(
    tmp_path: Path,
) -> None:
    explicit = _install_debugpy(tmp_path / "explicit" / ".venv.maya", "x = 1\n")
    other = _install_debugpy(tmp_path / "other" / ".venv.maya", "x = 1\n")
    found = _find_venv(
        explicit,
        {DEBUG_VENV_ENV: str(other)},
        origin=tmp_path / "missing.py",
        cwd=tmp_path,
    )
    assert found == explicit


def test_find_venv_refuses_the_only_copy_inside_maya(tmp_path: Path) -> None:
    maya = tmp_path / "Maya2027"
    (maya / "bin").mkdir(parents=True)
    (maya / "bin" / "mayapy.exe").write_bytes(b"")
    _install_debugpy(maya / ".venv.maya", "x = 1\n")
    origin = maya / "python" / "mtmaya" / "development" / "__init__.py"
    origin.parent.mkdir(parents=True)
    with pytest.raises(DevelopmentError, match="Maya's install"):
        _find_venv(None, {}, origin=origin, cwd=tmp_path / "else")


def test_find_venv_reads_the_environment_variable(tmp_path: Path) -> None:
    venv = _install_debugpy(tmp_path / ".venv.maya", "x = 1\n")
    found = _find_venv(
        None,
        {DEBUG_VENV_ENV: str(venv)},
        origin=tmp_path / "missing.py",
        cwd=tmp_path / "empty",
    )
    assert found == venv


def test_posix_site_packages_layout(tmp_path: Path, debugpy_modules: object) -> None:
    _ = debugpy_modules
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    venv = tmp_path / ".venv.maya"
    package = venv / "lib" / version / "site-packages" / "debugpy"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(_FAKE_DEBUGPY, encoding="utf-8")
    result = listen(venv=venv, environ={})
    assert result.venv == venv
    assert sys.modules["debugpy"].calls[1][2] is True
