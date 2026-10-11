"""Headless Maya scene for tool development.

Importing this module does not import Maya or start a session. Call
:func:`initialize` from ``mayapy``. The call opens an empty scene and leaves
startup scripts and plugin autoload alone.

When this module starts Maya, process exit turns undo off, calls
``maya.standalone.uninitialize``, and then :func:`os._exit`. A normal
interpreter shutdown hangs ``mayapy`` after that uninitialize. In a Maya
that is already running, :func:`initialize` does not change the scene and
does not exit the process.
"""

from __future__ import annotations

import atexit
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

__all__ = ["Session", "SessionError", "initialize", "uninitialize"]

_owned = False
_closed = False
_armed = False
_exit_status: int | None = None
_scene: str | None = None
_previous_exit: Callable[..., object] | None = None


class SessionError(Exception):
    """Raised when a headless Maya session cannot be started or closed."""


@dataclass(frozen=True, slots=True)
class Session:
    """A Maya scene opened for tool development.

    Attributes:
        started: True when this module called ``maya.standalone.initialize``.
        scene: Scene name returned by ``file -new``, or None when no scene
            was opened.
    """

    started: bool
    scene: str | None


def initialize(*, name: str = "python", new_scene: bool = True) -> Session:
    """Open a headless Maya scene.

    In ``mayapy``, this initializes standalone Maya and, by default, opens
    an empty scene. Process exit then uninitializes Maya and hard-exits.
    In a Maya that is already running, this returns without changing the
    scene and without installing that exit.

    Args:
        name: Application name passed to ``maya.standalone.initialize``.
        new_scene: Open an empty scene after this call starts Maya.

    Returns:
        Whether this module started Maya, and the new scene name.

    Raises:
        SessionError: If Maya cannot be initialized or the scene cannot
            be opened.
    """
    global _owned, _scene
    _require_name(name)
    if _session_is_up():
        log.debug("Maya is already running")
        return Session(started=_owned, scene=_scene if _owned else None)

    try:
        _standalone().initialize(name=name)
    except SessionError:
        raise
    except Exception as exc:
        if _session_is_up():
            log.debug("Maya was already initialized")
            return Session(started=False, scene=None)
        raise SessionError(f"Could not initialize Maya: {exc}") from exc

    _owned = True
    _arm_exit()
    if new_scene:
        _scene = _open_new_scene()
    log.info("Headless Maya scene is ready")
    return Session(started=True, scene=_scene)


def uninitialize(*, status: int = 0) -> None:
    """Uninitialize Maya if this module started it, then hard-exit.

    A Maya that was already running is left alone, and the process keeps
    going. ``os._exit`` skips the rest of interpreter shutdown.

    Args:
        status: Process status passed to ``os._exit``.

    Raises:
        SessionError: If ``status`` is not an integer.
    """
    code = _require_status(status)
    if not _owned:
        return
    _shutdown()
    _hard_exit(code)


def _on_exit() -> None:
    """Uninitialize on interpreter exit, then hard-exit with the stored code."""
    if not _owned:
        return
    _shutdown()
    _hard_exit(0 if _exit_status is None else _exit_status)


def _shutdown() -> None:
    global _closed
    if _closed:
        return
    _closed = True
    _disable_undo()
    log.info("Uninitializing headless Maya")
    try:
        _standalone().uninitialize()
    except Exception as exc:
        log.warning("Maya uninitialize failed: %s", exc)
    _flush_stdio()


def _arm_exit() -> None:
    global _armed, _previous_exit
    if _armed:
        return
    _previous_exit = sys.exit
    sys.exit = _installed_exit
    atexit.register(_on_exit)
    _armed = True


def _installed_exit(status: object = 0) -> None:
    _remember(status)
    if _previous_exit is None:
        raise SessionError("Maya exit hook is not installed.")
    _previous_exit(status)


def _remember(status: object) -> None:
    global _exit_status
    code = status.code if isinstance(status, SystemExit) else status
    if code is None:
        _exit_status = 0
    elif isinstance(code, int):
        _exit_status = int(code)
    else:
        _exit_status = 1


def _open_new_scene() -> str:
    try:
        result = _cmds().file(new=True, force=True)
    except SessionError:
        raise
    except Exception as exc:
        raise SessionError(f"Could not open a new scene: {exc}") from exc
    if result is None:
        return ""
    return str(result)


def _disable_undo() -> None:
    try:
        _cmds().undoInfo(state=False)
    except Exception as exc:
        log.debug("Could not turn undo off: %s", exc)


def _flush_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception as exc:
            log.debug("Could not flush stdio: %s", exc)


def _session_is_up() -> bool:
    try:
        cmds = _cmds()
    except SessionError:
        return False
    try:
        cmds.about(batch=True)
    except (AttributeError, RuntimeError):
        return False
    return True


def _require_name(name: str) -> None:
    if not isinstance(name, str) or name.strip() == "":
        raise SessionError("Pass a name for the Maya session.")


def _require_status(status: int) -> int:
    if isinstance(status, bool) or not isinstance(status, int):
        raise SessionError(f"Pass an exit status integer (got: {status!r}).")
    return status


def _cmds() -> Any:
    try:
        import maya.cmds as cmds
    except ImportError as exc:
        raise SessionError("Maya commands are not available.") from exc
    return cmds


def _standalone() -> Any:
    try:
        import maya.standalone as standalone
    except ImportError as exc:
        raise SessionError("Maya standalone is not available.") from exc
    return standalone


def _hard_exit(status: int) -> None:
    import os

    os._exit(status)


def _reset() -> None:
    """Clear session state. Tests use this so a hard exit is not installed."""
    global _owned, _closed, _armed, _exit_status, _scene, _previous_exit
    atexit.unregister(_on_exit)
    if _armed and _previous_exit is not None:
        sys.exit = _previous_exit
    _owned = False
    _closed = False
    _armed = False
    _exit_status = None
    _scene = None
    _previous_exit = None
