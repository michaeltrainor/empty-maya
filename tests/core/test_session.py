"""Tests for mtmaya.core.session. They do not launch Maya."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

import mtmaya.core.session as session
from mtmaya.core.session import Session, SessionError, initialize, uninitialize

ROOT = Path(__file__).resolve().parents[2]


class _Cmds:
    def __init__(self, *, running: bool = False) -> None:
        self.running = running
        self.calls: list[tuple[object, ...]] = []

    def about(self, **kwargs: object) -> bool:
        _ = kwargs
        if not self.running:
            raise RuntimeError("Maya is not initialized")
        return True

    def file(self, **kwargs: object) -> str:
        self.calls.append(("file", kwargs))
        self.running = True
        return "untitled"

    def undoInfo(self, **kwargs: object) -> None:
        self.calls.append(("undoInfo", kwargs))


class _Standalone:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[object, ...]] = []

    def initialize(self, name: str = "python") -> None:
        self.calls.append(("initialize", name))
        if self.fail is not None:
            raise self.fail

    def uninitialize(self) -> None:
        self.calls.append(("uninitialize",))


@pytest.fixture(autouse=True)
def _reset_session() -> object:
    session._reset()
    yield
    session._reset()


class _Hooks:
    def __init__(self) -> None:
        self.exits: list[int] = []
        self.registered: list[object] = []


def _install(
    monkeypatch: pytest.MonkeyPatch,
    cmds: _Cmds,
    standalone: _Standalone,
) -> _Hooks:
    hooks = _Hooks()
    monkeypatch.setattr(session, "_cmds", lambda: cmds)
    monkeypatch.setattr(session, "_standalone", lambda: standalone)
    monkeypatch.setattr(session.atexit, "register", hooks.registered.append)
    monkeypatch.setattr(session, "_hard_exit", hooks.exits.append)
    return hooks


def test_import_does_not_load_maya() -> None:
    assert "maya" not in sys.modules
    assert "maya.standalone" not in sys.modules
    assert "maya.cmds" not in sys.modules


def test_import_mtmaya_does_not_load_core() -> None:
    import mtmaya

    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "mtmaya.core" or name.startswith("mtmaya.core.")
    }
    for name in saved:
        del sys.modules[name]
    try:
        importlib.reload(mtmaya)
        assert "mtmaya.core" not in sys.modules
        assert "mtmaya.core.session" not in sys.modules
    finally:
        sys.modules.update(saved)
    tree = ast.parse((ROOT / "packages/mtmaya/src/mtmaya/__init__.py").read_text())
    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert "mtmaya.core" not in imported
    assert "mtmaya.core.session" not in imported


def test_user_setup_does_not_initialize() -> None:
    text = (
        ROOT / "packages/mtmaya-cli/src/mtmaya_cli/templates/module/userSetup.py.j2"
    ).read_text(encoding="utf-8")
    assert "core.session" not in text
    assert "maya.standalone" not in text


def test_session_does_not_source_startup_scripts() -> None:
    text = Path(session.__file__).read_text(encoding="utf-8")
    assert "userSetup" not in text
    assert "pluginPrefs" not in text
    assert "maya.mel" not in text


def test_initialize_opens_a_headless_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    result = initialize()
    assert result == Session(started=True, scene="untitled")
    assert standalone.calls == [("initialize", "python")]
    assert cmds.calls == [("file", {"new": True, "force": True})]
    assert hooks.exits == []
    assert hooks.registered == [session._on_exit]


def test_initialize_passes_the_application_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    _install(monkeypatch, cmds, standalone)
    initialize(name="tool", new_scene=False)
    assert standalone.calls == [("initialize", "tool")]
    assert cmds.calls == []


def test_initialize_leaves_a_running_maya_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds(running=True)
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    result = initialize()
    assert result == Session(started=False, scene=None)
    assert standalone.calls == []
    assert cmds.calls == []
    assert hooks.exits == []
    assert hooks.registered == []
    uninitialize()
    assert hooks.exits == []


def test_second_initialize_does_not_start_maya_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    first = initialize()
    cmds.running = True
    second = initialize()
    assert first == Session(started=True, scene="untitled")
    assert second == Session(started=True, scene="untitled")
    assert standalone.calls == [("initialize", "python")]
    assert hooks.registered == [session._on_exit]


def test_initialize_requires_a_name(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    _install(monkeypatch, cmds, standalone)
    with pytest.raises(SessionError, match="name"):
        initialize(name="  ")
    assert standalone.calls == []


def test_initialize_reports_a_missing_maya(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing() -> object:
        raise SessionError("Maya standalone is not available.")

    monkeypatch.setattr(session, "_cmds", missing)
    monkeypatch.setattr(session, "_standalone", missing)
    with pytest.raises(SessionError, match="not available"):
        initialize()
    assert session._armed is False


def test_initialize_reports_a_failed_start(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds = _Cmds()
    standalone = _Standalone(fail=RuntimeError("license"))
    _install(monkeypatch, cmds, standalone)
    with pytest.raises(SessionError, match="license"):
        initialize()
    assert session._owned is False
    assert session._armed is False


def test_initialize_treats_an_existing_session_as_already_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()

    def about(**kwargs: object) -> bool:
        _ = kwargs
        cmds.running = True
        if len(cmds.calls) == 0:
            cmds.calls.append(("about",))
            raise RuntimeError("Maya is already initialized")
        return True

    cmds.about = about  # type: ignore[method-assign]
    standalone = _Standalone(fail=RuntimeError("Maya is already initialized"))
    hooks = _install(monkeypatch, cmds, standalone)
    result = initialize()
    assert result == Session(started=False, scene=None)
    assert session._armed is False
    assert hooks.exits == []
    assert hooks.registered == []


def test_new_scene_failure_still_arms_the_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()

    def file(**kwargs: object) -> str:
        _ = kwargs
        raise RuntimeError("disk")

    cmds.file = file  # type: ignore[method-assign]
    standalone = _Standalone()
    _install(monkeypatch, cmds, standalone)
    with pytest.raises(SessionError, match="new scene"):
        initialize()
    assert session._owned is True
    assert session._armed is True


def test_uninitialize_turns_undo_off_and_hard_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    initialize(new_scene=False)
    uninitialize(status=3)
    assert ("undoInfo", {"state": False}) in cmds.calls
    assert standalone.calls == [("initialize", "python"), ("uninitialize",)]
    assert hooks.exits == [3]
    uninitialize(status=4)
    assert hooks.exits == [3, 4]
    assert standalone.calls.count(("uninitialize",)) == 1


def test_exit_hook_keeps_the_sys_exit_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    initialize(new_scene=False)
    with pytest.raises(SystemExit):
        sys.exit(2)
    session._on_exit()
    assert standalone.calls[-1] == ("uninitialize",)
    assert hooks.exits == [2]


def test_exit_hook_uses_zero_when_the_process_falls_off_the_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    initialize(new_scene=False)
    session._on_exit()
    assert hooks.exits == [0]


def test_string_exit_status_becomes_one(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    initialize(new_scene=False)
    with pytest.raises(SystemExit):
        sys.exit("boom")
    session._on_exit()
    assert hooks.exits == [1]


def test_uninitialize_rejects_a_boolean_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmds = _Cmds()
    standalone = _Standalone()
    hooks = _install(monkeypatch, cmds, standalone)
    initialize(new_scene=False)
    with pytest.raises(SessionError, match="integer"):
        uninitialize(status=True)  # type: ignore[arg-type]
    assert hooks.exits == []
    assert ("uninitialize",) not in standalone.calls
