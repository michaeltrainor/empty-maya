"""Core helpers for the Maya runtime.

UI entry points live in :mod:`mtmaya.core.ui`. A headless scene lives in
:mod:`mtmaya.core.session`. Importing this package does not import Maya
or Qt.
"""

from __future__ import annotations

from mtmaya.core.session import Session, SessionError, initialize, uninitialize

__all__ = ["Session", "SessionError", "initialize", "uninitialize"]
