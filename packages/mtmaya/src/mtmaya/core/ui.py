"""Maya UI helpers for Qt wrapping, menus, and shelves.

Importing this module does not import Maya, PySide6, or shiboken6. Maya
ships those modules. Functions import them when called.

Qt helpers wrap Maya's OpenMayaUI pointers as the matching PySide6 type:
the main window as ``QMainWindow``, controls as ``QWidget``, layouts as
``QLayout``, and menu items as ``QAction``. Menus and shelf buttons are
not Qt widgets. They are built with ``maya.cmds`` and, where Maya only
exposes a global procedure, ``maya.mel``.

Other Maya UI commands, such as windows and panels, stay on ``maya.cmds``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication, QLayout, QMainWindow, QWidget

log = logging.getLogger(__name__)

SourceType = Literal["python", "mel"]
_SOURCE_TYPES: frozenset[str] = frozenset({"python", "mel"})

__all__ = [
    "UiError",
    "add_divider",
    "add_menu_item",
    "add_shelf_button",
    "create_menu",
    "create_shelf",
    "current_parent",
    "defer",
    "delete_shelf",
    "delete_ui",
    "main_window_name",
    "maya_main_window",
    "qapplication",
    "save_shelves",
    "shelf_layout_name",
    "ui_path",
    "wrap_control",
    "wrap_instance",
    "wrap_layout",
    "wrap_menu_item",
]


class UiError(Exception):
    """Raised when Maya UI cannot be queried or changed."""


def maya_main_window() -> QMainWindow:
    """Return Maya's main window as a ``QMainWindow``.

    Parent tool widgets to this window so they stay above Maya and close
    with the session.

    Returns:
        The Maya main window.

    Raises:
        UiError: If Maya or PySide6 is missing, or the window pointer is null.
    """
    raw = _main_window_pointer()
    if raw is None:
        raise UiError("Maya main window is not available.")
    log.debug("Wrapping Maya main window pointer %s", raw)
    return wrap_instance(raw, _qmain_window_type())


def qapplication() -> QApplication:
    """Return the ``QApplication`` running inside Maya.

    This does not create an application. Maya already owns one.

    Returns:
        The running application.

    Raises:
        UiError: If PySide6 is missing or no application is running.
    """
    try:
        app = _qapplication_instance()
    except ImportError as exc:
        raise UiError(
            "PySide6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    if app is None:
        raise UiError("No QApplication is running.")
    log.debug("Using the running QApplication")
    return app


def current_parent() -> QWidget:
    """Return the Maya layout currently receiving child controls.

    Call this while Maya is building a ``cmds`` layout to parent a Qt
    widget into that layout.

    Returns:
        The current parent as a ``QWidget``.

    Raises:
        UiError: If Maya is not building UI, or Qt is unavailable.
    """
    raw = _current_parent_pointer()
    if raw is None:
        raise UiError("Maya has no current UI parent.")
    log.debug("Wrapping Maya current parent pointer %s", raw)
    return wrap_instance(raw, _qwidget_type())


def wrap_instance[T](ptr: int, qt_type: type[T]) -> T:
    """Wrap a Maya C++ Qt pointer as a PySide6 instance.

    Args:
        ptr: Address from ``MQtUtil``. Pass ``int(pointer)`` for Swig
            pointer objects.
        qt_type: PySide6 type to wrap as, such as ``QWidget`` or ``QAction``.

    Returns:
        The wrapped PySide6 object.

    Raises:
        UiError: If ``ptr`` is null, shiboken6 is missing, or wrapping fails.
    """
    if not ptr:
        raise UiError("Cannot wrap a null Qt pointer.")
    type_name = getattr(qt_type, "__name__", qt_type)
    log.debug("Wrapping Qt pointer %s as %s", ptr, type_name)
    try:
        wrapped = _shiboken_wrap(int(ptr), qt_type)
    except ImportError as exc:
        raise UiError(
            "shiboken6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    except (TypeError, ValueError) as exc:
        raise UiError(f"Failed to wrap Qt pointer: {exc}") from exc
    if wrapped is None:
        raise UiError("Failed to wrap Qt pointer.")
    return wrapped


def wrap_control(name: str) -> QWidget:
    """Wrap a Maya control name as a ``QWidget``.

    Args:
        name: Maya UI path, such as ``modelPanel1``.

    Returns:
        The wrapped control.

    Raises:
        UiError: If the control does not exist or Qt is unavailable.
    """
    return _wrap_named(name, "findControl", _qwidget_type, "control")


def wrap_layout(name: str) -> QLayout:
    """Wrap a Maya layout name as a ``QLayout``.

    Args:
        name: Maya UI path, such as ``formLayout1``.

    Returns:
        The wrapped layout.

    Raises:
        UiError: If the layout does not exist or Qt is unavailable.
    """
    return _wrap_named(name, "findLayout", _qlayout_type, "layout")


def wrap_menu_item(name: str) -> QAction:
    """Wrap a Maya menu item name as a ``QAction``.

    Args:
        name: Maya menu item path.

    Returns:
        The wrapped action.

    Raises:
        UiError: If the menu item does not exist or Qt is unavailable.
    """
    return _wrap_named(name, "findMenuItem", _qaction_type, "menu item")


def ui_path(widget: object) -> str:
    """Return the Maya UI path for a wrapped Qt object.

    Args:
        widget: PySide6 object previously wrapped from a Maya pointer.

    Returns:
        Maya's full UI path, such as ``MayaWindow|formLayout1``.

    Raises:
        UiError: If the object has no Maya path, or Qt is unavailable.
    """
    ptr = _cpp_pointer(widget)
    try:
        name = _full_name(ptr)
    except ImportError as exc:
        raise UiError("Maya Qt is not available.") from exc
    if not name:
        raise UiError("Qt object has no Maya UI path.")
    log.debug("Maya UI path for pointer %s is %s", ptr, name)
    return name


def defer(callback: Callable[[], object]) -> None:
    """Run ``callback`` on Maya's idle queue.

    UI built during startup must wait until Maya has created the main
    window. ``maya.utils.executeDeferred`` schedules that work.

    Args:
        callback: Callable with no arguments. Use a lambda to bind arguments.

    Raises:
        UiError: If Maya is not available.
    """
    log.debug("Deferring %s", getattr(callback, "__name__", callback))
    try:
        _maya_utils().executeDeferred(callback)
    except ImportError as exc:
        raise UiError("Maya is not available.") from exc
    except RuntimeError as exc:
        raise UiError(f"Failed to defer UI work: {exc}") from exc


def main_window_name() -> str:
    """Return the Maya main window control name.

    This is the ``cmds`` name from the MEL global ``$gMainWindow``, not a
    Qt widget. Use :func:`maya_main_window` when a tool needs the
    ``QMainWindow``.

    Returns:
        Control name, usually ``MayaWindow``.

    Raises:
        UiError: If Maya MEL is unavailable or the global is empty.
    """
    name = _mel_global("gMainWindow")
    if not name:
        raise UiError("Maya main window is not available.")
    log.debug("Maya main window name is %s", name)
    return name


def shelf_layout_name() -> str:
    """Return the Maya shelf tab layout name.

    This is the ``cmds`` name from the MEL global ``$gShelfTopLevel``.

    Returns:
        Shelf layout name.

    Raises:
        UiError: If Maya MEL is unavailable or the global is empty.
    """
    name = _mel_global("gShelfTopLevel")
    if not name:
        raise UiError("Maya shelf layout is not available.")
    log.debug("Maya shelf layout name is %s", name)
    return name


def create_menu(
    label: str,
    *,
    parent: str | None = None,
    name: str | None = None,
    tear_off: bool = True,
    replace: bool = False,
) -> str:
    """Create a menu with ``cmds.menu``.

    Args:
        label: Menu label shown in the menu bar.
        parent: Parent menu bar. ``None`` uses :func:`main_window_name`.
        name: Explicit Maya object name. ``None`` lets Maya assign one.
            Required when ``replace`` is true.
        tear_off: When true, the menu can be torn off.
        replace: When true, delete an existing menu with ``name`` first.

    Returns:
        The menu name.

    Raises:
        UiError: If Maya rejects the menu, or ``replace`` is set without a name.
    """
    menu_label = _require_text(label, "menu label")
    parent_name = main_window_name() if parent is None else parent
    _require_text(parent_name, "menu parent")
    if replace:
        if name is None:
            raise UiError("Replacing a menu requires a name.")
        _delete_menu_if_present(name)
    kwargs: dict[str, object] = {
        "parent": parent_name,
        "label": menu_label,
        "tearOff": tear_off,
    }
    if name is None:
        created = _ui_call("create menu", _cmds().menu, **kwargs)
    else:
        created = _ui_call("create menu", _cmds().menu, name, **kwargs)
    log.info("Created menu %r under %s", menu_label, parent_name)
    return created


def add_menu_item(
    parent: str,
    label: str,
    command: str | None = None,
    *,
    source_type: SourceType = "python",
    name: str | None = None,
    image: str | None = None,
    annotation: str | None = None,
    sub_menu: bool = False,
    option_box: bool = False,
    tear_off: bool = False,
) -> str:
    """Add a ``cmds.menuItem`` under ``parent``.

    Args:
        parent: Menu or submenu that receives the item.
        label: Item label.
        command: Python or MEL statement run when the item is chosen.
            Required unless ``sub_menu`` is true.
        source_type: ``python`` or ``mel``. Maya's own default is MEL.
            This defaults to ``python``.
        name: Explicit Maya object name. ``None`` lets Maya assign one.
        image: Icon name. ``None`` omits the icon.
        annotation: Status-line help. ``None`` omits it.
        sub_menu: When true, the item opens a submenu. Parent later items
            to the returned name.
        option_box: When true, the item is the option box for the previous
            menu item.
        tear_off: When true with ``sub_menu``, the submenu can be torn off.

    Returns:
        The menu item name.

    Raises:
        UiError: If the arguments conflict or Maya rejects the item.
    """
    if sub_menu and option_box:
        raise UiError("A menu item cannot be both a submenu and an option box.")
    if command is None and not sub_menu:
        raise UiError("A menu item requires a command.")
    language = _source_type(source_type)
    item_label = _require_text(label, "menu item label")
    parent_name = _require_text(parent, "menu parent")
    kwargs: dict[str, object] = {
        "parent": parent_name,
        "label": item_label,
        "sourceType": language,
        "subMenu": sub_menu,
        "optionBox": option_box,
    }
    if command is not None:
        kwargs["command"] = command
    if sub_menu:
        kwargs["tearOff"] = tear_off
    if image is not None:
        kwargs["image"] = image
    if annotation is not None:
        kwargs["annotation"] = annotation
    if name is None:
        created = _ui_call("add menu item", _cmds().menuItem, **kwargs)
    else:
        created = _ui_call("add menu item", _cmds().menuItem, name, **kwargs)
    log.info("Added menu item %r under %s (%s)", item_label, parent_name, language)
    return created


def add_divider(parent: str) -> str:
    """Add a divider to a menu.

    Args:
        parent: Menu or submenu that receives the divider.

    Returns:
        The divider item name.

    Raises:
        UiError: If Maya rejects the divider.
    """
    parent_name = _require_text(parent, "menu parent")
    log.debug("Adding menu divider under %s", parent_name)
    return _ui_call(
        "add menu divider",
        _cmds().menuItem,
        parent=parent_name,
        divider=True,
    )


def delete_ui(name: str) -> None:
    """Delete a Maya UI element by control name.

    Use this for menus and other ``cmds`` UI. Shelf tabs use
    :func:`delete_shelf`, which also updates Maya's shelf bar.

    Args:
        name: Maya UI path or object name.

    Raises:
        UiError: If Maya cannot delete the element.
    """
    ui_name = _require_text(name, "UI")
    try:
        _cmds().deleteUI(ui_name)
    except RuntimeError as exc:
        raise UiError(f"Failed to delete UI {ui_name!r}: {exc}") from exc
    log.info("Deleted UI %s", ui_name)


def create_shelf(name: str, *, replace: bool = False) -> str:
    """Create a shelf tab, or return it when it already exists.

    New tabs are created with the MEL procedure ``addNewShelfTab``. Buttons
    on the tab are added with :func:`add_shelf_button`.

    Args:
        name: Shelf tab name.
        replace: When true, delete an existing tab before creating it.

    Returns:
        The shelf layout name.

    Raises:
        UiError: If Maya cannot query or create the shelf.
    """
    shelf = _require_text(name, "shelf")
    try:
        exists = bool(_cmds().shelfLayout(shelf, exists=True))
    except RuntimeError as exc:
        raise UiError(f"Failed to query shelf {shelf!r}: {exc}") from exc
    if exists and not replace:
        log.debug("Shelf %s already exists", shelf)
        return shelf
    if exists:
        delete_shelf(shelf)
    created = _mel_eval(f"addNewShelfTab {_mel_string(shelf)}")
    shelf_name = created or shelf
    log.info("Created shelf %s", shelf_name)
    return shelf_name


def add_shelf_button(
    parent: str,
    label: str,
    command: str,
    *,
    source_type: SourceType = "python",
    image: str = "commandButton.png",
    annotation: str | None = None,
    overlay: str | None = None,
    name: str | None = None,
) -> str:
    """Add a ``cmds.shelfButton`` to a shelf.

    Args:
        parent: Shelf layout name from :func:`create_shelf`.
        label: Button label.
        command: Python or MEL statement run when the button is pressed.
        source_type: ``python`` or ``mel``. Maya's own default is MEL.
            This defaults to ``python``.
        image: Icon name. Defaults to Maya's ``commandButton.png``.
        annotation: Tooltip text. ``None`` omits it.
        overlay: Short text drawn on the icon. ``None`` omits it.
        name: Explicit Maya object name. ``None`` lets Maya assign one.

    Returns:
        The shelf button name.

    Raises:
        UiError: If Maya rejects the button.
    """
    language = _source_type(source_type)
    shelf = _require_text(parent, "shelf")
    button_label = _require_text(label, "shelf button label")
    kwargs: dict[str, object] = {
        "parent": shelf,
        "label": button_label,
        "command": command,
        "sourceType": language,
        "image": image,
    }
    if annotation is not None:
        kwargs["annotation"] = annotation
    if overlay is not None:
        kwargs["imageOverlayLabel"] = overlay
    if name is None:
        created = _ui_call("add shelf button", _cmds().shelfButton, **kwargs)
    else:
        created = _ui_call("add shelf button", _cmds().shelfButton, name, **kwargs)
    log.info("Added shelf button %r to %s (%s)", button_label, shelf, language)
    return created


def delete_shelf(name: str) -> None:
    """Remove a shelf tab with the MEL procedure ``deleteShelfTab``.

    Args:
        name: Shelf tab name.

    Raises:
        UiError: If Maya cannot delete the shelf.
    """
    shelf = _require_text(name, "shelf")
    _mel_eval(f"deleteShelfTab {_mel_string(shelf)}")
    log.info("Deleted shelf %s", shelf)


def save_shelves() -> None:
    """Write the current shelves with the MEL procedure ``saveAllShelves``.

    Raises:
        UiError: If Maya cannot save shelves.
    """
    _mel_eval("saveAllShelves")
    log.info("Saved Maya shelves")


def _wrap_named[T](
    name: str,
    finder: str,
    type_factory: Callable[[], type[T]],
    kind: str,
) -> T:
    raw = _find_pointer(name, finder)
    if raw is None:
        raise UiError(f"Maya {kind} not found: {name}")
    log.debug("Wrapping Maya %s %s pointer %s", kind, name, raw)
    return wrap_instance(raw, type_factory())


def _main_window_pointer() -> int | None:
    try:
        omui = _open_maya_ui()
    except ImportError as exc:
        raise UiError("Maya Qt is not available.") from exc
    return _as_pointer(omui.MQtUtil.mainWindow())


def _current_parent_pointer() -> int | None:
    try:
        omui = _open_maya_ui()
    except ImportError as exc:
        raise UiError("Maya Qt is not available.") from exc
    return _as_pointer(omui.MQtUtil.getCurrentParent())


def _find_pointer(name: str, finder: str) -> int | None:
    try:
        omui = _open_maya_ui()
    except ImportError as exc:
        raise UiError("Maya Qt is not available.") from exc
    return _as_pointer(getattr(omui.MQtUtil, finder)(name))


def _full_name(ptr: int) -> str | None:
    omui = _open_maya_ui()
    name = omui.MQtUtil.fullName(ptr)
    if not name:
        return None
    return str(name)


def _as_pointer(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        ptr = int(cast(Any, raw))
    except (TypeError, ValueError) as exc:
        raise UiError(
            f"Maya returned a pointer that is not an integer: {raw!r}"
        ) from exc
    if not ptr:
        return None
    return ptr


def _open_maya_ui() -> Any:
    from maya import OpenMayaUI as omui

    return omui


def _shiboken_wrap[T](ptr: int, qt_type: type[T]) -> T:
    from shiboken6 import wrapInstance

    return wrapInstance(ptr, qt_type)


def _get_cpp_pointer(widget: object) -> tuple[int, ...]:
    from shiboken6 import getCppPointer

    return getCppPointer(widget)


def _cpp_pointer(widget: object) -> int:
    try:
        pointers = _get_cpp_pointer(widget)
    except ImportError as exc:
        raise UiError(
            "shiboken6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    except (TypeError, RuntimeError) as exc:
        raise UiError(f"Failed to read a Qt pointer: {exc}") from exc
    if not pointers or pointers[0] is None:
        raise UiError("Qt object has no C++ pointer.")
    return int(pointers[0])


def _qapplication_instance() -> QApplication | None:
    from PySide6.QtWidgets import QApplication

    return QApplication.instance()


def _qmain_window_type() -> type[QMainWindow]:
    from PySide6.QtWidgets import QMainWindow

    return QMainWindow


def _qwidget_type() -> type[QWidget]:
    from PySide6.QtWidgets import QWidget

    return QWidget


def _qlayout_type() -> type[QLayout]:
    from PySide6.QtWidgets import QLayout

    return QLayout


def _qaction_type() -> type[QAction]:
    from PySide6.QtGui import QAction

    return QAction


def _maya_utils() -> Any:
    import maya.utils as utils

    return utils


def _cmds() -> Any:
    try:
        import maya.cmds as cmds
    except ImportError as exc:
        raise UiError("Maya commands are not available.") from exc
    return cmds


def _mel() -> Any:
    try:
        import maya.mel as mel
    except ImportError as exc:
        raise UiError("Maya MEL is not available.") from exc
    return mel


def _mel_global(name: str) -> str:
    """Return a Maya MEL global string.

    The ``$name=$name`` form assigns the global to itself so ``eval``
    yields the current value.
    """
    if not name.isidentifier():
        raise UiError(f"Invalid MEL global name: {name}")
    return _mel_eval(f"${name}=${name}")


def _mel_eval(code: str) -> str:
    try:
        result = _mel().eval(code)
    except RuntimeError as exc:
        raise UiError(f"MEL command failed: {exc}") from exc
    if result is None:
        return ""
    return str(result)


def _mel_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _source_type(source_type: str) -> str:
    if source_type not in _SOURCE_TYPES:
        raise UiError(
            f"Command source type must be 'python' or 'mel', got {source_type!r}."
        )
    return source_type


def _require_text(value: str, kind: str) -> str:
    if not value or not value.strip():
        raise UiError(f"A {kind} is required.")
    return value


def _delete_menu_if_present(name: str) -> None:
    menu_name = _require_text(name, "menu name")
    try:
        exists = bool(_cmds().menu(menu_name, exists=True))
    except RuntimeError as exc:
        raise UiError(f"Failed to query menu {menu_name!r}: {exc}") from exc
    if not exists:
        return
    log.debug("Deleting existing menu %s", menu_name)
    delete_ui(menu_name)


def _ui_call(
    action: str,
    func: Callable[..., object],
    *args: object,
    **kwargs: object,
) -> str:
    try:
        result = func(*args, **kwargs)
    except RuntimeError as exc:
        raise UiError(f"Failed to {action}: {exc}") from exc
    if result is None or result == "":
        raise UiError(f"Failed to {action}.")
    return str(result)
