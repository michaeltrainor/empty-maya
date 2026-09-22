"""Example dialog parented to the Maya main window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mtmaya_qt.host import QtError, maya_main_window

if TYPE_CHECKING:
    from PySide6.QtWidgets import QDialog, QWidget

log = logging.getLogger(__name__)


def hello_dialog(*, parent: QWidget | None = None) -> QDialog:
    """Build an example dialog parented to the Maya main window.

    The dialog is not shown. Call ``show()`` on the result from a tool command.

    Args:
        parent: Widget to parent to. ``None`` uses :func:`maya_main_window`.

    Returns:
        A dialog titled ``mtmaya-qt``.

    Raises:
        QtError: If Qt or the Maya main window is unavailable.
    """
    owner = maya_main_window() if parent is None else parent
    try:
        from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
    except ImportError as exc:
        raise QtError(
            "PySide6 is not available. Use the Qt bindings that ship with Maya."
        ) from exc
    dialog = QDialog(owner)
    dialog.setObjectName("mtmayaQtHelloDialog")
    dialog.setWindowTitle("mtmaya-qt")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Shared Maya Qt lives in mtmaya-qt."))
    log.debug("Built example dialog %s", dialog.objectName())
    return dialog
