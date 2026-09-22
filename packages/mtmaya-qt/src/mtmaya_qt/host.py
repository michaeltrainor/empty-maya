"""Maya Qt entry points: main window, QApplication, and pointer wrapping.

Functions import ``maya``, ``PySide6``, and ``shiboken6`` only when called.
Maya already ships those modules. This package does not install them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget

log = logging.getLogger(__name__)


class QtError(Exception):
    """Raised when Maya Qt is unavailable or a pointer cannot be wrapped."""


def maya_main_window(
    *,
    pointer: Callable[[], int | None] | None = None,
    wrap: Callable[[int, type[QWidget]], QWidget] | None = None,
    widget_type: type[QWidget] | None = None,
) -> QWidget:
    """Return Maya's main window as a ``QWidget``.

    Parent tool widgets to this window so they stay above Maya and close
    with the session.

    Args:
        pointer: Lookup for the main-window address. ``None`` uses
            ``maya.OpenMayaUI.MQtUtil.mainWindow``.
        wrap: Pointer wrapper. ``None`` uses :func:`shiboken6.wrapInstance`.
        widget_type: Type to wrap as. ``None`` uses ``QWidget``.

    Returns:
        The Maya main window.

    Raises:
        QtError: If Maya or PySide6 is missing, or the window pointer is null.
    """
    lookup = pointer or _main_window_pointer
    try:
        raw = lookup()
    except ImportError as exc:
        raise QtError("Maya Qt is not available.") from exc
    if raw is None:
        raise QtError("Maya main window is not available.")
    qt_type = widget_type or _qt_type("PySide6.QtWidgets", "QWidget")
    log.debug("Wrapping Maya main window pointer %s", raw)
    return wrap_instance(int(raw), qt_type, wrap=wrap)


def qapplication(
    *,
    instance: Callable[[], QApplication | None] | None = None,
) -> QApplication:
    """Return the ``QApplication`` running inside Maya.

    Args:
        instance: Lookup for the application. ``None`` uses
            ``QApplication.instance``.

    Returns:
        The running application.

    Raises:
        QtError: If PySide6 is missing or no application is running.
    """
    getter = instance or _qapplication_instance
    try:
        app = getter()
    except ImportError as exc:
        raise QtError(
            "PySide6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    if app is None:
        raise QtError("No QApplication is running.")
    return app


def wrap_instance[T](
    ptr: int,
    qt_type: type[T],
    *,
    wrap: Callable[[int, type[T]], T] | None = None,
) -> T:
    """Wrap a Maya C++ Qt pointer as a PySide6 instance.

    Args:
        ptr: Address from ``MQtUtil`` (``int(pointer)``).
        qt_type: PySide6 type to wrap as, such as ``QWidget``.
        wrap: Wrapper implementation. ``None`` uses
            :func:`shiboken6.wrapInstance`.

    Returns:
        The wrapped PySide6 object.

    Raises:
        QtError: If ``ptr`` is null, shiboken6 is missing, or wrapping fails.
    """
    if not ptr:
        raise QtError("Cannot wrap a null Qt pointer.")
    wrapper = wrap or _shiboken_wrap
    try:
        wrapped = wrapper(int(ptr), qt_type)
    except ImportError as exc:
        raise QtError(
            "shiboken6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    except (TypeError, ValueError) as exc:
        raise QtError(f"Failed to wrap Qt pointer: {exc}") from exc
    if wrapped is None:
        raise QtError("Failed to wrap Qt pointer.")
    return wrapped


def wrap_control(
    name: str,
    *,
    find: Callable[[str], int | None] | None = None,
    wrap: Callable[[int, type[QWidget]], QWidget] | None = None,
    widget_type: type[QWidget] | None = None,
) -> QWidget:
    """Wrap a Maya control name as a ``QWidget``.

    Args:
        name: Maya UI path, such as ``modelPanel1``.
        find: Control lookup. ``None`` uses ``MQtUtil.findControl``.
        wrap: Pointer wrapper. ``None`` uses :func:`shiboken6.wrapInstance`.
        widget_type: Type to wrap as. ``None`` uses ``QWidget``.

    Returns:
        The wrapped control.

    Raises:
        QtError: If the control does not exist or Qt is unavailable.
    """
    lookup = find or _find_control
    try:
        raw = lookup(name)
    except ImportError as exc:
        raise QtError("Maya Qt is not available.") from exc
    if raw is None:
        raise QtError(f"Maya control not found: {name}")
    qt_type = widget_type or _qt_type("PySide6.QtWidgets", "QWidget")
    log.debug("Wrapping Maya control %s pointer %s", name, raw)
    return wrap_instance(int(raw), qt_type, wrap=wrap)


def _main_window_pointer() -> int | None:
    from maya import OpenMayaUI as omui

    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return int(ptr)


def _find_control(name: str) -> int | None:
    from maya import OpenMayaUI as omui

    ptr = omui.MQtUtil.findControl(name)
    if ptr is None:
        return None
    return int(ptr)


def _qapplication_instance() -> QApplication | None:
    from PySide6.QtWidgets import QApplication

    return QApplication.instance()


def _shiboken_wrap[T](ptr: int, qt_type: type[T]) -> T:
    from shiboken6 import wrapInstance

    return wrapInstance(ptr, qt_type)


def _qt_type(module: str, name: str) -> type:
    try:
        imported = __import__(module, fromlist=[name])
    except ImportError as exc:
        raise QtError(
            "PySide6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    try:
        return getattr(imported, name)
    except AttributeError as exc:
        raise QtError(f"{module}.{name} is not available.") from exc
