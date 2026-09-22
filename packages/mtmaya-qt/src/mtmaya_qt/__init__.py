"""Shared Maya and PySide6 widgets for game-development tools.

Importing this package does not import Maya or PySide6. Call
:func:`maya_main_window` when a tool needs the Maya window. Maya ships
Qt; this package does not depend on PyPI ``PySide6``.

Attributes:
    __version__: Installed package version, or ``0.0.0`` if metadata is missing.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version

from mtmaya_qt.host import (
    QtError,
    maya_main_window,
    qapplication,
    wrap_control,
    wrap_instance,
)

try:
    __version__ = version("mtmaya-qt")
except PackageNotFoundError:
    __version__ = "0.0.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "QtError",
    "__version__",
    "maya_main_window",
    "qapplication",
    "wrap_control",
    "wrap_instance",
]
