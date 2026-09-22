"""Host entry points stay usable without launching Maya."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from mtmaya_qt import (
    QtError,
    maya_main_window,
    qapplication,
    wrap_control,
    wrap_instance,
)
from mtmaya_qt.examples.hello import hello_dialog

QT_ROOT = (
    Path(__file__).resolve().parents[2] / "packages" / "mtmaya-qt" / "src" / "mtmaya_qt"
)


def test_import_does_not_load_maya_or_qt() -> None:
    import importlib

    import mtmaya_qt

    before = {name for name in ("maya", "PySide6", "shiboken6") if name in sys.modules}
    importlib.reload(mtmaya_qt)
    after = {name for name in ("maya", "PySide6", "shiboken6") if name in sys.modules}
    assert after == before
    assert mtmaya_qt.maya_main_window is maya_main_window


def test_qt_sources_import_maya_only_inside_functions() -> None:
    for path in QT_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _runtime_imports(tree):
            assert name not in {"maya", "PySide6", "shiboken6"}, path


def test_maya_main_window_wraps_injected_pointer() -> None:
    seen: list[tuple[int, type]] = []

    def wrap(ptr: int, qt_type: type) -> dict[str, int | type]:
        seen.append((ptr, qt_type))
        return {"ptr": ptr, "type": qt_type}

    widget = maya_main_window(pointer=lambda: 42, wrap=wrap, widget_type=dict)
    assert widget == {"ptr": 42, "type": dict}
    assert seen == [(42, dict)]


def test_maya_main_window_rejects_null_pointer() -> None:
    with pytest.raises(QtError, match="not available"):
        maya_main_window(
            pointer=lambda: None,
            wrap=lambda ptr, qt_type: object(),
            widget_type=dict,
        )


def test_wrap_instance_rejects_null() -> None:
    with pytest.raises(QtError, match="null"):
        wrap_instance(0, dict)


def test_wrap_instance_uses_injected_wrapper() -> None:
    wrapped = wrap_instance(7, dict, wrap=lambda ptr, qt_type: (ptr, qt_type))
    assert wrapped == (7, dict)


def test_qapplication_requires_a_running_app() -> None:
    with pytest.raises(QtError, match="No QApplication"):
        qapplication(instance=lambda: None)


def test_qapplication_returns_injected_app() -> None:
    app = object()
    assert qapplication(instance=lambda: app) is app


def test_wrap_control_wraps_injected_pointer() -> None:
    widget = wrap_control(
        "modelPanel1",
        find=lambda name: 9 if name == "modelPanel1" else None,
        wrap=lambda ptr, qt_type: (ptr, qt_type),
        widget_type=dict,
    )
    assert widget == (9, dict)


def test_wrap_control_missing_name() -> None:
    with pytest.raises(QtError, match="modelPanel1"):
        wrap_control(
            "modelPanel1",
            find=lambda name: None,
            wrap=lambda ptr, qt_type: object(),
            widget_type=dict,
        )


def test_hello_dialog_requires_qt(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("no PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(QtError, match="PySide6"):
        hello_dialog(parent=object())


def _runtime_imports(tree: ast.AST) -> list[str]:
    """Return import roots that execute when the module is imported."""
    names: list[str] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[ast.AST] = []

        def visit(self, node: ast.AST) -> None:
            self.stack.append(node)
            super().visit(node)
            self.stack.pop()

        def visit_Import(self, node: ast.Import) -> None:
            if not _inside_function(self.stack) and not _inside_type_checking(
                self.stack
            ):
                names.extend(alias.name.split(".")[0] for alias in node.names)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if (
                node.module
                and not _inside_function(self.stack)
                and not _inside_type_checking(self.stack)
            ):
                names.append(node.module.split(".")[0])

    Visitor().visit(tree)
    return names


def _inside_function(stack: list[ast.AST]) -> bool:
    return any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) for node in stack
    )


def _inside_type_checking(stack: list[ast.AST]) -> bool:
    for node in stack:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
            return True
    return False
