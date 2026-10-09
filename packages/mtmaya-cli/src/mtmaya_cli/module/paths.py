"""Maya user-module locations."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from mtmaya_cli.module import ModuleError

DEFAULT_MAYA_VERSION = "2027"
"""Maya year used when a specifier or CLI override does not name one."""


def default_maya_app_dir() -> Path:
    """Return the platform default for ``MAYA_APP_DIR``.

    Returns:
        macOS: ``~/Library/Preferences/Autodesk/maya``. Windows:
        ``~/Documents/maya``. Linux and other POSIX: ``~/maya``.
    """
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Preferences" / "Autodesk" / "maya"
    if sys.platform == "win32":
        return home / "Documents" / "maya"
    return home / "maya"


def maya_app_dir(*, environ: Mapping[str, str] | None = None) -> Path:
    """Return Maya's application-directory root.

    Reads ``MAYA_APP_DIR`` from ``environ`` (or the process environment). When
    that variable is unset or empty, uses :func:`default_maya_app_dir`.

    Args:
        environ: Environment mapping. ``None`` reads ``os.environ``. Pass a
            mapping (including ``{}``) in tests so live ``MAYA_APP_DIR`` is
            ignored.

    Returns:
        Absolute or as-given path to the Maya app dir.
    """
    env: Mapping[str, str] = os.environ if environ is None else environ
    raw = env.get("MAYA_APP_DIR", "")
    if raw:
        return Path(raw)
    return default_maya_app_dir()


def user_modules_dir(
    *,
    maya_version: str = DEFAULT_MAYA_VERSION,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the versioned Maya user modules directory.

    Args:
        maya_version: Maya year subdirectory, e.g. ``2027``.
        environ: Environment mapping for ``MAYA_APP_DIR``. ``None`` reads
            ``os.environ``.

    Returns:
        ``$MAYA_APP_DIR/{maya_version}/modules``.
    """
    return maya_app_dir(environ=environ) / maya_version / "modules"


def maya_module_platform() -> str:
    """Return the Maya ``PLATFORM`` tag for this operating system.

    Maya skips a ``.mod`` entry whose ``PLATFORM`` does not match the host.
    The tags are ``win64``, ``mac``, and ``linux``.

    Returns:
        The tag for ``sys.platform``.

    Raises:
        ModuleError: If this host has no Maya platform tag.
    """
    if sys.platform == "win32":
        return "win64"
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("linux"):
        return "linux"
    raise ModuleError(f"Unsupported platform for Maya modules: {sys.platform}")


def default_pointer_path(
    name: str,
    *,
    maya_version: str = DEFAULT_MAYA_VERSION,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the default sibling ``.mod`` path for a module name.

    Args:
        name: Maya module name (no spaces).
        maya_version: Maya year subdirectory, e.g. ``2027``.
        environ: Environment mapping for ``MAYA_APP_DIR``. ``None`` reads
            ``os.environ``.

    Returns:
        ``{user_modules_dir}/{name}.mod``.
    """
    return user_modules_dir(maya_version=maya_version, environ=environ) / f"{name}.mod"
