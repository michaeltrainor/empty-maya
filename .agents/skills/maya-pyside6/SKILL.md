---
name: maya-pyside6
description: >
  Build and test Autodesk Maya tools that use PySide6 with mtmaya and mtqt.
  Covers mtmaya.core.ui host helpers and pytest-qt (qtbot) tests that do not
  launch Maya. Use when adding or changing Maya UI, PySide6 widgets, menus,
  shelves, or tests for a tool built with mtmaya, or when the user runs
  /maya-pyside6.
---

# Maya PySide6

Use this when building a Maya tool UI on mtmaya, or when testing one.

## Runtime

Maya 2027+ ships PySide6 and shiboken6. Do not pip install PyPI PySide6 into Maya, and do not install into Maya's `site-packages`. `strip_pyside` in `packages/mtmaya-cli/src/mtmaya_cli/module/package.py` removes PySide6 and shiboken6 after `uv pip install --target`.

`import mtmaya` must not import Maya, PySide6, shiboken6, or mtqt. Inside `packages/mtmaya`, import those only inside functions. `tests/module/test_imports.py` enforces that.

Host API is `mtmaya.core.ui`. Read that module for signatures. Callers follow these rules:

- Give a tool window an optional `parent`. The launcher passes `maya_main_window()`. Tests construct the window with no parent.
- Call `qapplication()` to use Maya's application. Never construct `QApplication` inside Maya.
- Call `defer()` from `userSetup` so the main window exists before showing UI.
- Build menus and shelves with `create_menu`, `add_menu_item`, `add_divider`, `create_shelf`, `add_shelf_button`, `delete_shelf`, `save_shelves`, and `delete_ui`. `source_type` is `"python"` or `"mel"`.
- Use `mtqt` for shared widgets. The workspace path dependency is in the root `pyproject.toml`. Import `mtqt` from the tool, not from `mtmaya/__init__.py`.
- Raise `UiError` when the host call fails. Log with `logging.getLogger(__name__)`. Google-style docstrings and type annotations on public functions.

```python
def show_tool() -> ToolWindow:
    window = ToolWindow(maya_main_window())
    window.show()
    return window
```

## Tests

`uv run pytest` must pass without launching Maya. `@pytest.mark.maya` is skipped when `import maya` fails. Do not run that marker from a git hook. `maya.standalone.initialize()` checks out a license.

Dev dependencies include `pytest` and `pytest-qt`. `qt_api` is `pyside6` in the root `pyproject.toml`. `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` before pytest-qt imports PySide6. The dev env's PySide6 comes from `mtqt`. That is the binding widget tests use. It is not Maya's build.

**Host calls** (pointer wrap, menus, shelves): monkeypatch `mtmaya.core.ui` and do not request `qtbot`. Copy `tests/core/test_ui.py`.

**Widget behavior**: construct the tool with no parent and request `qtbot`. pytest-qt creates the one `QApplication` for the session. Do not construct another.

- `qtbot.addWidget` on every widget the test creates.
- Drive the widget with `qtbot.mouseClick`, `qtbot.keyClicks`, and `qtbot.keyPress`.
- Assert signals with `with qtbot.waitSignal(signal)`.
- Use `qtbot.waitUntil` instead of sleeping. Do not require a mapped window. Offscreen has no display.
- If the test calls the launcher, monkeypatch `maya_main_window` and `maya.cmds` before that call so Maya is not imported.
- Do not request `qtbot` from a `@pytest.mark.maya` test. pytest-qt would open a second application. A live Maya test uses the application Maya already created.

```python
def test_apply_emits_name(qtbot):
    from PySide6.QtCore import Qt

    window = ToolWindow()
    qtbot.addWidget(window)
    window.name.setText("hero")
    with qtbot.waitSignal(window.nameAccepted) as blocker:
        qtbot.mouseClick(window.apply_button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["hero"]
```

Run one module with `uv run pytest tests/path/test_tool.py`.
