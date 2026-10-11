"""Remote debugging for Maya.

Import this module explicitly. ``import mtmaya`` does not load it, and
``userSetup.py`` must not call :func:`listen`.

:func:`listen` starts an in-process debugpy adapter and loads ``debugpy``
from ``.venv.maya``. The same call works under ``mayapy`` and inside a
running Maya, whose executable is ``maya`` rather than Python. A spawned
adapter would try to execute that binary, and Maya's ``site-packages``
does not contain ``debugpy``.

Attach a debugpy client to the returned host and port. Map the checkout's
``packages/mtmaya/src/mtmaya`` to the installed module's ``python/mtmaya``.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

DEBUG_VENV_ENV = "MTMAYA_DEBUG_VENV"
_VENV_DIRNAME = ".venv.maya"

__all__ = ["DEBUG_VENV_ENV", "DebugListen", "DevelopmentError", "listen"]


class DevelopmentError(Exception):
    """Raised when a debug session cannot be started."""


@dataclass(frozen=True, slots=True)
class DebugListen:
    """A debugpy listener waiting for an IDE to attach.

    Attributes:
        host: Interface the adapter is listening on.
        port: TCP port the adapter is listening on.
        venv: ``.venv.maya`` directory that supplied ``debugpy``.
        waiting: True when the call blocked until a client attached.
    """

    host: str
    port: int
    venv: Path
    waiting: bool


def listen(
    host: str = "127.0.0.1",
    port: int = 5678,
    *,
    wait: bool = False,
    venv: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> DebugListen:
    """Listen for a debugger to attach to this process.

    From Maya's Script Editor, call this and leave ``wait`` false so the
    UI stays responsive. From ``mayapy``, pass ``wait=True`` so the
    process stays up until the IDE attaches. ``wait=True`` in the Script
    Editor blocks Maya until then.

    Args:
        host: Interface to bind. The default is ``127.0.0.1``.
        port: TCP port. ``0`` asks the operating system for a free port.
        wait: Block until a client attaches.
        venv: ``.venv.maya`` that contains ``debugpy``. Discovered when
            omitted.
        environ: Environment mapping. ``None`` reads ``os.environ``.
            ``MTMAYA_DEBUG_VENV`` names the virtual environment.

    Returns:
        The host, port, and environment that are listening.

    Raises:
        DevelopmentError: If ``debugpy`` cannot be loaded from
            ``.venv.maya`` or the listener cannot start.
    """
    _validate_endpoint(host, port)
    found = _find_venv(venv, environ, origin=Path(__file__), cwd=Path.cwd())
    debugpy = _load_debugpy(found)
    try:
        # In-process so this works for mayapy and for a running maya.exe.
        # debugpy's spawned adapter would execute sys.executable, which is
        # maya.exe in the GUI, and that interpreter does not see .venv.maya.
        debugpy.configure(subProcess=False)
        endpoint = debugpy.listen((host, port), in_process_debug_adapter=True)
        if wait:
            log.info("Waiting for a debugger to attach")
            debugpy.wait_for_client()
    except (RuntimeError, ValueError, TypeError) as exc:
        raise DevelopmentError(str(exc)) from exc

    actual_host, actual_port = _endpoint(endpoint)
    log.info("Listening for a debugger on %s:%s", actual_host, actual_port)
    return DebugListen(
        host=actual_host,
        port=actual_port,
        venv=found,
        waiting=wait,
    )


def _validate_endpoint(host: str, port: int) -> None:
    if not isinstance(host, str) or host.strip() == "":
        raise DevelopmentError("Pass a host for the debugger to listen on.")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise DevelopmentError(
            f"Pass a debugger port from 0 through 65535 (got: {port})."
        )


def _find_venv(
    venv: Path | None,
    environ: Mapping[str, str] | None,
    *,
    origin: Path,
    cwd: Path,
) -> Path:
    """Return the ``.venv.maya`` directory that contains ``debugpy``."""
    if venv is not None:
        return _require_venv(Path(venv))

    env: Mapping[str, str] = os.environ if environ is None else environ
    raw = env.get(DEBUG_VENV_ENV, "").strip()
    if raw:
        return _require_venv(Path(raw))

    blocked: Path | None = None
    seen: set[Path] = set()
    for start in (origin, cwd):
        current = start if start.is_dir() else start.parent
        for root in (current, *current.parents):
            if root in seen:
                continue
            seen.add(root)
            candidate = root / _VENV_DIRNAME
            if _site_packages(candidate) is None:
                continue
            maya_root = _maya_install(candidate)
            if maya_root is not None:
                blocked = maya_root
                continue
            return candidate
    if blocked is not None:
        raise DevelopmentError(
            f"Refusing to load debugpy from Maya's install at {blocked}."
        )
    raise DevelopmentError(
        "Pass venv or set MTMAYA_DEBUG_VENV to a .venv.maya that has debugpy installed."
    )


def _require_venv(venv: Path) -> Path:
    if _site_packages(venv) is None:
        raise DevelopmentError(f"debugpy is not installed in {venv}.")
    maya_root = _maya_install(venv)
    if maya_root is not None:
        raise DevelopmentError(
            f"Refusing to load debugpy from Maya's install at {maya_root}."
        )
    return venv


def _site_packages(venv: Path) -> Path | None:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = (
        venv / "Lib" / "site-packages",
        venv / "lib" / version / "site-packages",
    )
    for candidate in candidates:
        init = candidate / "debugpy" / "__init__.py"
        if init.is_file():
            return candidate
    return None


def _maya_install(path: Path) -> Path | None:
    """Return the Maya root when ``path`` lives inside a Maya install."""
    current = path if path.is_dir() else path.parent
    for parent in (current, *current.parents):
        bindir = parent / "bin"
        if (bindir / "mayapy.exe").is_file() or (bindir / "mayapy").is_file():
            return parent
    return None


def _load_debugpy(venv: Path) -> object:
    site = _site_packages(venv)
    if site is None:
        raise DevelopmentError(f"debugpy is not installed in {venv}.")
    existing = sys.modules.get("debugpy")
    existing_file = (
        getattr(existing, "__file__", None) if existing is not None else None
    )
    if existing is not None and (
        existing_file is None or not _inside(Path(existing_file), site)
    ):
        raise DevelopmentError(
            f"debugpy is already loaded from outside .venv.maya ({existing_file})."
        )

    inserted = False
    site_key = os.path.normcase(str(site))
    if not any(os.path.normcase(entry) == site_key for entry in sys.path):
        sys.path.insert(0, str(site))
        inserted = True
    try:
        module = importlib.import_module("debugpy")
    except ImportError as exc:
        if inserted:
            _drop_path(site_key)
        raise DevelopmentError(f"Could not import debugpy from {venv}.") from exc

    location = getattr(module, "__file__", None)
    if (
        location is None
        or not _inside(Path(location), site)
        or _maya_install(Path(location)) is not None
    ):
        if inserted:
            _drop_path(site_key)
        sys.modules.pop("debugpy", None)
        raise DevelopmentError(f"debugpy did not load from {venv}.")
    return module


def _drop_path(site_key: str) -> None:
    sys.path[:] = [entry for entry in sys.path if os.path.normcase(entry) != site_key]


def _inside(child: Path, parent: Path) -> bool:
    child_s = os.path.normcase(os.path.abspath(child))
    parent_s = os.path.normcase(os.path.abspath(parent)).rstrip("\\/")
    return child_s == parent_s or child_s.startswith(parent_s + os.sep)


def _endpoint(endpoint: object) -> tuple[str, int]:
    if (
        isinstance(endpoint, tuple)
        and len(endpoint) == 2
        and isinstance(endpoint[0], str)
        and isinstance(endpoint[1], int)
        and not isinstance(endpoint[1], bool)
    ):
        return endpoint[0], endpoint[1]
    raise DevelopmentError("debugpy.listen did not return a host and port.")
