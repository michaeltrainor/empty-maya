"""Maya UI helpers stay importable without launching Maya."""

from __future__ import annotations

import builtins
import importlib
import logging
import sys

import pytest

from mtmaya.core import ui


class Pointer:
    def __int__(self) -> int:
        return 42


class QtUtil:
    def __init__(self) -> None:
        self.main: object = Pointer()
        self.parent: object = 4
        self.controls = {"modelPanel1": 9}
        self.layouts = {"formLayout1": 8}
        self.items = {"item1": 7}
        self.names = {9: "MayaWindow|modelPanel1"}

    def mainWindow(self) -> object:
        return self.main

    def getCurrentParent(self) -> object:
        return self.parent

    def findControl(self, name: str) -> object:
        return self.controls.get(name)

    def findLayout(self, name: str) -> object:
        return self.layouts.get(name)

    def findMenuItem(self, name: str) -> object:
        return self.items.get(name)

    def fullName(self, ptr: int) -> str | None:
        return self.names.get(ptr)


class Omui:
    def __init__(self, qt: QtUtil | None = None) -> None:
        self.MQtUtil = qt or QtUtil()


class FakeCmds:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.menus: set[str] = set()
        self.shelves: set[str] = set()
        self.fail = False
        self.fail_query = False

    def menu(self, *args: object, **kwargs: object) -> object:
        self.calls.append(("menu", args, kwargs))
        if self.fail and not kwargs.get("exists"):
            raise RuntimeError("menu failed")
        if kwargs.get("exists"):
            return args[0] in self.menus
        created = args[0] if args else "menu1"
        self.menus.add(str(created))
        return created

    def menuItem(self, *args: object, **kwargs: object) -> object:
        self.calls.append(("menuItem", args, kwargs))
        if self.fail:
            raise RuntimeError("item failed")
        if not args and not kwargs.get("divider"):
            return kwargs.get("label", "item")
        if args:
            return args[0]
        return "divider1"

    def deleteUI(self, name: str) -> None:
        self.calls.append(("deleteUI", name))
        if self.fail:
            raise RuntimeError("missing")
        self.menus.discard(name)

    def shelfLayout(self, name: str, exists: bool = False) -> bool:
        self.calls.append(("shelfLayout", name, exists))
        if self.fail_query:
            raise RuntimeError("query failed")
        return name in self.shelves

    def shelfButton(self, *args: object, **kwargs: object) -> object:
        self.calls.append(("shelfButton", args, kwargs))
        if self.fail:
            raise RuntimeError("button failed")
        return args[0] if args else kwargs["label"]


class FakeMel:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.values = {
            "$gMainWindow=$gMainWindow": "MayaWindow",
            "$gShelfTopLevel=$gShelfTopLevel": "ShelfLayout",
        }
        self.created = "Tools"
        self.error: RuntimeError | None = None

    def eval(self, code: str) -> str:
        self.calls.append(code)
        if self.error is not None:
            raise self.error
        if code in self.values:
            return self.values[code]
        if code.startswith("addNewShelfTab"):
            return self.created
        return ""


class FakeUtils:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def executeDeferred(self, callback: object) -> None:
        self.calls.append(callback)


def test_import_does_not_load_maya_or_qt() -> None:
    watched = ("maya", "PySide6", "shiboken6")
    before = {name for name in watched if name in sys.modules}
    importlib.reload(ui)
    after = {name for name in watched if name in sys.modules}
    assert after == before


def test_maya_main_window_wraps_swig_pointer(monkeypatch: pytest.MonkeyPatch) -> None:
    qt = _patch_qt(monkeypatch)
    window = ui.maya_main_window()
    assert window == (42, "QMainWindow")
    assert qt.mainWindow() == qt.main


def test_maya_main_window_rejects_null(monkeypatch: pytest.MonkeyPatch) -> None:
    qt = _patch_qt(monkeypatch)
    qt.main = 0
    with pytest.raises(ui.UiError, match="not available"):
        ui.maya_main_window()


def test_maya_main_window_rejects_non_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    qt = _patch_qt(monkeypatch)
    qt.main = "nope"
    with pytest.raises(ui.UiError, match="not an integer"):
        ui.maya_main_window()


def test_maya_main_window_requires_maya(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "maya")
    with pytest.raises(ui.UiError, match="Maya Qt"):
        ui.maya_main_window()


def test_qapplication_returns_injected_app(monkeypatch: pytest.MonkeyPatch) -> None:
    app = object()
    monkeypatch.setattr(ui, "_qapplication_instance", lambda: app)
    assert ui.qapplication() is app


def test_qapplication_requires_a_running_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui, "_qapplication_instance", lambda: None)
    with pytest.raises(ui.UiError, match="No QApplication"):
        ui.qapplication()


def test_qapplication_requires_pyside(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "PySide6")
    with pytest.raises(ui.UiError, match="PySide6"):
        ui.qapplication()


def test_current_parent_wraps_pointer(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_qt(monkeypatch)
    assert ui.current_parent() == (4, "QWidget")


def test_current_parent_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    qt = _patch_qt(monkeypatch)
    qt.parent = None
    with pytest.raises(ui.UiError, match="current UI parent"):
        ui.current_parent()


def test_wrap_instance_rejects_null() -> None:
    with pytest.raises(ui.UiError, match="null"):
        ui.wrap_instance(0, dict)


def test_wrap_instance_missing_shiboken(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "shiboken6")
    with pytest.raises(ui.UiError, match="shiboken6"):
        ui.wrap_instance(3, dict)


def test_wrap_instance_reports_wrapper_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(ptr: int, qt_type: type[object]) -> object:
        _ = ptr, qt_type
        raise TypeError("bad pointer")

    monkeypatch.setattr(ui, "_shiboken_wrap", explode)
    with pytest.raises(ui.UiError, match="bad pointer"):
        ui.wrap_instance(3, dict)


def test_wrap_instance_rejects_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui, "_shiboken_wrap", lambda ptr, qt_type: None)
    with pytest.raises(ui.UiError, match="Failed to wrap"):
        ui.wrap_instance(3, dict)


def test_wrap_named_uses_matching_qt_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_qt(monkeypatch)
    assert ui.wrap_control("modelPanel1") == (9, "QWidget")
    assert ui.wrap_layout("formLayout1") == (8, "QLayout")
    assert ui.wrap_menu_item("item1") == (7, "QAction")


def test_wrap_control_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_qt(monkeypatch)
    with pytest.raises(ui.UiError, match="modelPanel4"):
        ui.wrap_control("modelPanel4")


def test_ui_path_reads_full_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_qt(monkeypatch)
    monkeypatch.setattr(ui, "_get_cpp_pointer", lambda widget: (9,))
    assert ui.ui_path(object()) == "MayaWindow|modelPanel1"


def test_ui_path_missing_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_qt(monkeypatch)
    monkeypatch.setattr(ui, "_get_cpp_pointer", lambda widget: (1,))
    with pytest.raises(ui.UiError, match="no Maya UI path"):
        ui.ui_path(object())


def test_ui_path_missing_pointer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui, "_get_cpp_pointer", lambda widget: ())
    with pytest.raises(ui.UiError, match="no C\\+\\+ pointer"):
        ui.ui_path(object())


def test_ui_path_requires_shiboken(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "shiboken6")
    with pytest.raises(ui.UiError, match="shiboken6"):
        ui.ui_path(object())


def test_defer_schedules_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    utils = FakeUtils()
    monkeypatch.setattr(ui, "_maya_utils", lambda: utils)

    def work() -> None:
        return None

    ui.defer(work)
    assert utils.calls == [work]


def test_defer_requires_maya(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "maya")
    with pytest.raises(ui.UiError, match="Maya is not available"):
        ui.defer(lambda: None)


def test_main_window_and_shelf_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _cmds, mel = _install(monkeypatch)
    assert ui.main_window_name() == "MayaWindow"
    assert ui.shelf_layout_name() == "ShelfLayout"
    assert mel.calls == [
        "$gMainWindow=$gMainWindow",
        "$gShelfTopLevel=$gShelfTopLevel",
    ]


def test_main_window_name_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _cmds, mel = _install(monkeypatch)
    mel.values["$gMainWindow=$gMainWindow"] = ""
    with pytest.raises(ui.UiError, match="not available"):
        ui.main_window_name()


def test_create_menu_defaults_to_main_window(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, mel = _install(monkeypatch)
    assert ui.create_menu("Tools") == "menu1"
    assert mel.calls == ["$gMainWindow=$gMainWindow"]
    kind, _args, kwargs = cmds.calls[-1]
    assert kind == "menu"
    assert kwargs["parent"] == "MayaWindow"
    assert kwargs["label"] == "Tools"
    assert kwargs["tearOff"] is True


def test_create_menu_replaces_named_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    cmds.menus.add("toolsMenu")
    created = ui.create_menu(
        "Tools",
        parent="MayaWindow",
        name="toolsMenu",
        replace=True,
    )
    assert created == "toolsMenu"
    assert ("deleteUI", "toolsMenu") in cmds.calls
    assert "toolsMenu" in cmds.menus


def test_create_menu_replace_requires_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    with pytest.raises(ui.UiError, match="requires a name"):
        ui.create_menu("Tools", parent="MayaWindow", replace=True)


def test_create_menu_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    cmds.fail = True
    with pytest.raises(ui.UiError, match="menu failed"):
        ui.create_menu("Tools", parent="MayaWindow")


def test_add_menu_item_python_and_mel(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    assert ui.add_menu_item("ToolsMenu", "Run", "print(1)") == "Run"
    assert (
        ui.add_menu_item(
            "ToolsMenu",
            "Query",
            "print 1;",
            source_type="mel",
            image="commandButton.png",
            annotation="Query the scene",
            name="queryItem",
        )
        == "queryItem"
    )
    python_item = cmds.calls[0][2]
    mel_item = cmds.calls[1][2]
    assert python_item["sourceType"] == "python"
    assert python_item["command"] == "print(1)"
    assert mel_item["sourceType"] == "mel"
    assert mel_item["image"] == "commandButton.png"
    assert cmds.calls[1][1] == ("queryItem",)


def test_add_menu_item_submenu(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    assert ui.add_menu_item("ToolsMenu", "More", sub_menu=True, tear_off=True) == "More"
    kwargs = cmds.calls[-1][2]
    assert kwargs["subMenu"] is True
    assert kwargs["tearOff"] is True
    assert "command" not in kwargs


def test_add_menu_item_rejects_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    with pytest.raises(ui.UiError, match="submenu"):
        ui.add_menu_item(
            "ToolsMenu",
            "More",
            "print(1)",
            sub_menu=True,
            option_box=True,
        )
    with pytest.raises(ui.UiError, match="requires a command"):
        ui.add_menu_item("ToolsMenu", "Run")
    with pytest.raises(ui.UiError, match="source type"):
        ui.add_menu_item("ToolsMenu", "Run", "print(1)", source_type="pymel")  # type: ignore[arg-type]


def test_add_divider(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    assert ui.add_divider("ToolsMenu") == "divider1"
    assert cmds.calls[-1][2]["divider"] is True


def test_delete_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    ui.delete_ui("ToolsMenu")
    assert cmds.calls == [("deleteUI", "ToolsMenu")]
    cmds.fail = True
    with pytest.raises(ui.UiError, match="missing"):
        ui.delete_ui("ToolsMenu")


def test_create_shelf_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, mel = _install(monkeypatch)
    cmds.shelves.add("Tools")
    assert ui.create_shelf("Tools") == "Tools"
    assert mel.calls == []


def test_create_shelf_replace_uses_mel(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, mel = _install(monkeypatch)
    cmds.shelves.add('tool"box')
    assert ui.create_shelf('tool"box', replace=True) == "Tools"
    assert mel.calls == [
        'deleteShelfTab "tool\\"box"',
        'addNewShelfTab "tool\\"box"',
    ]


def test_create_shelf_query_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    cmds.fail_query = True
    with pytest.raises(ui.UiError, match="query failed"):
        ui.create_shelf("Tools")


def test_add_shelf_button(monkeypatch: pytest.MonkeyPatch) -> None:
    cmds, _mel = _install(monkeypatch)
    assert ui.add_shelf_button("Tools", "Run", "print(1)", overlay="Run") == "Run"
    kwargs = cmds.calls[-1][2]
    assert kwargs["sourceType"] == "python"
    assert kwargs["image"] == "commandButton.png"
    assert kwargs["imageOverlayLabel"] == "Run"
    assert kwargs["command"] == "print(1)"


def test_delete_and_save_shelves(monkeypatch: pytest.MonkeyPatch) -> None:
    _cmds, mel = _install(monkeypatch)
    ui.delete_shelf("Tools")
    ui.save_shelves()
    assert mel.calls == ['deleteShelfTab "Tools"', "saveAllShelves"]
    mel.error = RuntimeError("mel failed")
    with pytest.raises(ui.UiError, match="mel failed"):
        ui.save_shelves()


def test_blank_names_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    with pytest.raises(ui.UiError, match="menu label"):
        ui.create_menu("  ", parent="MayaWindow")
    with pytest.raises(ui.UiError, match="shelf"):
        ui.create_shelf("")


def test_menu_creation_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _install(monkeypatch)
    with caplog.at_level(logging.INFO, logger="mtmaya.core.ui"):
        ui.create_menu("Tools", parent="MayaWindow")
    assert "Created menu 'Tools' under MayaWindow" in caplog.text


def test_wrap_is_logged_at_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_qt(monkeypatch)
    with caplog.at_level(logging.DEBUG, logger="mtmaya.core.ui"):
        ui.wrap_control("modelPanel1")
    assert "modelPanel1" in caplog.text


def _install(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeCmds, FakeMel]:
    cmds = FakeCmds()
    mel = FakeMel()
    monkeypatch.setattr(ui, "_cmds", lambda: cmds)
    monkeypatch.setattr(ui, "_mel", lambda: mel)
    return cmds, mel


def _patch_qt(monkeypatch: pytest.MonkeyPatch) -> QtUtil:
    qt = QtUtil()
    monkeypatch.setattr(ui, "_open_maya_ui", lambda: Omui(qt))
    monkeypatch.setattr(ui, "_shiboken_wrap", lambda ptr, qt_type: (ptr, qt_type))
    monkeypatch.setattr(ui, "_qmain_window_type", lambda: "QMainWindow")
    monkeypatch.setattr(ui, "_qwidget_type", lambda: "QWidget")
    monkeypatch.setattr(ui, "_qlayout_type", lambda: "QLayout")
    monkeypatch.setattr(ui, "_qaction_type", lambda: "QAction")
    return qt


def _block_import(monkeypatch: pytest.MonkeyPatch, root: str) -> None:
    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == root or name.startswith(f"{root}."):
            raise ImportError(f"no {root}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
