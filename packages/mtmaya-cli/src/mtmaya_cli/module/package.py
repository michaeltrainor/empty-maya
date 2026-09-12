"""Install the ``mtmaya`` runtime as a Maya module.

Scaffolds the stock module tree via :func:`create_module`, then installs
the ``mtmaya`` distribution into ``python/`` with ``uv pip install
--target``. Does not import ``maya``.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from mtmaya import __version__
from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.modfile import render_modfile
from mtmaya_cli.module.paths import DEFAULT_MAYA_VERSION, user_modules_dir
from mtmaya_cli.module.scaffold import create_module

MODULE_NAME = "mtmaya"
"""Maya module name and destination folder under ``modules/``."""

RUNTIME_DIST_NAME = "mtmaya"
"""PyPI / workspace distribution installed into the module ``python/`` dir."""

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PackageInstallResult:
    """Outcome of installing ``mtmaya`` as a Maya module.

    Attributes:
        path: Destination sibling ``.mod`` path (Maya scans this file).
        root: Destination module tree (sibling of ``path``).
        contents: Text written to ``path``.
    """

    path: Path
    root: Path
    contents: str


@dataclass(frozen=True, slots=True)
class PackageUninstallResult:
    """Outcome of removing an installed ``mtmaya`` Maya module.

    Attributes:
        path: Sibling ``.mod`` path that was or would have been removed.
        root: Module tree that was or would have been removed.
        removed: True when at least one of ``path`` or ``root`` existed.
    """

    path: Path
    root: Path
    removed: bool


def find_uv() -> str:
    """Return the ``uv`` executable path.

    Returns:
        Absolute or PATH-resolved ``uv`` command.

    Raises:
        ModuleError: If ``uv`` is not on ``PATH``.
    """
    uv = shutil.which("uv")
    if uv:
        return uv
    fallback = Path.home() / ".local" / "bin" / "uv"
    if fallback.is_file():
        return str(fallback)
    raise ModuleError("uv is required to install mtmaya into a Maya module.")


def runtime_requirement() -> str:
    """Return a pip/uv requirement for the installed ``mtmaya`` distribution.

    Prefers the editable or wheel origin from ``direct_url.json`` so a
    workspace checkout installs itself. Falls back to ``mtmaya==version``.

    Returns:
        A local project path or ``mtmaya==<version>``.

    Raises:
        ModuleError: If the ``mtmaya`` distribution is not installed.
    """
    try:
        dist = distribution(RUNTIME_DIST_NAME)
    except PackageNotFoundError as exc:
        raise ModuleError("Cannot locate the mtmaya distribution.") from exc
    origin = _direct_url_path(dist)
    if origin is not None:
        return str(origin)
    return f"{RUNTIME_DIST_NAME}=={dist.version}"


def uv_pip_install(
    spec: str,
    target: Path,
    *,
    argv: Sequence[str] | None = None,
) -> list[str]:
    """Install a requirement into ``target`` with ``uv pip install --target``.

    Wipes nothing; callers replace ``target`` first. Strips PySide6 after
    install so Maya's bundled Qt is not shadowed.

    Args:
        spec: Requirement or local project path.
        target: Destination directory for the installed graph.
        argv: Optional prebuilt command (tests). ``None`` builds the default.

    Returns:
        The command that was run.

    Raises:
        ModuleError: If ``uv`` is missing or the install fails.
    """
    cmd = list(argv) if argv is not None else _default_uv_pip_cmd(spec, target)
    log.info("Installing runtime with %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except OSError as exc:
        raise ModuleError(f"Failed to run uv pip install: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or str(exc)
        raise ModuleError(f"Failed to install {spec} into {target}: {detail}") from exc
    strip_pyside(target)
    return cmd


def install_runtime(python_dir: Path, *, spec: str | None = None) -> list[str]:
    """Replace ``python_dir`` with the ``mtmaya`` runtime graph.

    Args:
        python_dir: Module ``python/`` directory.
        spec: Install requirement. ``None`` uses :func:`runtime_requirement`.

    Returns:
        The ``uv pip install`` command that was run.

    Raises:
        ModuleError: If the install fails.
    """
    requirement = spec if spec is not None else runtime_requirement()
    if python_dir.exists():
        shutil.rmtree(python_dir)
    python_dir.mkdir(parents=True, exist_ok=True)
    return uv_pip_install(requirement, python_dir)


def strip_pyside(target: Path) -> None:
    """Remove PySide6 / shiboken trees so they cannot shadow Maya's Qt.

    Args:
        target: ``--target`` directory after ``uv pip install``.
    """
    if not target.is_dir():
        return
    for child in target.iterdir():
        name = child.name
        if name.startswith(("PySide6", "shiboken6")):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            log.debug("Removed forbidden Qt package %s", child)


def render_package_modfile(
    *,
    version: str,
    module_root: Path,
    maya_version: str = DEFAULT_MAYA_VERSION,
) -> str:
    """Return ``.mod`` text via :func:`render_modfile` plus ``PYTHONPATH``.

    Maya maps ``scripts/`` automatically. ``python/`` is not a stock module
    folder, so the extra line puts it on ``PYTHONPATH``.

    Args:
        version: Package version written into the specifier.
        module_root: Module tree (the ``mtmaya/`` folder next to the
            ``.mod`` file).
        maya_version: Maya year for ``MAYAVERSION``.

    Returns:
        ``.mod`` file text with a trailing newline and no blank lines.
    """
    return render_modfile(
        name=MODULE_NAME,
        version=version,
        maya_version=maya_version,
        module_path=str(module_root.resolve()),
        extra_lines=("PYTHONPATH +:= python",),
    )


def modules_dir(
    *,
    maya_version: str = DEFAULT_MAYA_VERSION,
    app_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the versioned Maya user modules directory.

    Args:
        maya_version: Maya year subdirectory, e.g. ``2027``.
        app_dir: Override for ``MAYA_APP_DIR``. ``None`` uses ``environ``.
        environ: Environment mapping for ``MAYA_APP_DIR``. ``None`` reads
            ``os.environ``.

    Returns:
        ``{app_dir}/{maya_version}/modules``.
    """
    if app_dir is not None:
        return Path(app_dir).expanduser() / maya_version / "modules"
    return user_modules_dir(maya_version=maya_version, environ=environ)


def install_package(
    *,
    maya_version: str = DEFAULT_MAYA_VERSION,
    app_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
    version: str | None = None,
    spec: str | None = None,
) -> PackageInstallResult:
    """Scaffold a Maya module and install the ``mtmaya`` runtime graph.

    Replaces an existing install of the same name. Uses
    :func:`create_module` for stock folders and ``userSetup.py``, then
    ``uv pip install --target`` into ``python/``.

    Args:
        maya_version: Maya year subdirectory, e.g. ``2027``.
        app_dir: Override for ``MAYA_APP_DIR``. ``None`` uses ``environ``.
        environ: Environment mapping for ``MAYA_APP_DIR``. ``None`` reads
            ``os.environ``.
        version: Version written into the ``.mod``. ``None`` uses the
            installed package version.
        spec: Requirement passed to ``uv pip install``. ``None`` uses
            :func:`runtime_requirement`.

    Returns:
        Destination ``.mod`` path, module tree, and file contents.

    Raises:
        ModuleError: If scaffolding or the runtime install fails.
    """
    dest_dir = modules_dir(maya_version=maya_version, app_dir=app_dir, environ=environ)
    dest_root = dest_dir / MODULE_NAME
    dest_mod = dest_dir / f"{MODULE_NAME}.mod"
    python_dir = dest_root / "python"

    ver = version if version is not None else __version__
    contents = render_package_modfile(
        version=ver, module_root=dest_root, maya_version=maya_version
    )

    log.info("Installing %s %s to %s", MODULE_NAME, ver, dest_dir)
    try:
        if dest_root.exists():
            shutil.rmtree(dest_root)
        if dest_mod.exists() or dest_mod.is_symlink():
            dest_mod.unlink()
        create_module(
            MODULE_NAME,
            directory=dest_dir,
            version=ver,
            maya_version=maya_version,
            with_user_setup=True,
            startup_import=MODULE_NAME,
        )
        (dest_root / f"{MODULE_NAME}.mod").unlink(missing_ok=True)
        install_runtime(python_dir, spec=spec)
        dest_mod.write_text(contents, encoding="utf-8")
    except ModuleError:
        raise
    except OSError as exc:
        raise ModuleError(
            f"Failed to install {MODULE_NAME} to {dest_dir}: {exc}"
        ) from exc
    log.debug("Wrote .mod %s", dest_mod)
    return PackageInstallResult(path=dest_mod, root=dest_root, contents=contents)


def uninstall_package(
    *,
    maya_version: str = DEFAULT_MAYA_VERSION,
    app_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> PackageUninstallResult:
    """Remove the installed ``mtmaya`` module tree and sibling ``.mod``.

    Missing installs are a no-op (``removed`` is False). Other files in
    ``modules/`` are left untouched.

    Args:
        maya_version: Maya year subdirectory, e.g. ``2027``.
        app_dir: Override for ``MAYA_APP_DIR``. ``None`` uses ``environ``.
        environ: Environment mapping for ``MAYA_APP_DIR``. ``None`` reads
            ``os.environ``.

    Returns:
        Paths considered and whether anything was removed.

    Raises:
        ModuleError: If removal I/O fails.
    """
    dest_dir = modules_dir(maya_version=maya_version, app_dir=app_dir, environ=environ)
    dest_root = dest_dir / MODULE_NAME
    dest_mod = dest_dir / f"{MODULE_NAME}.mod"
    removed = dest_root.exists() or dest_mod.exists()
    log.info("Uninstalling %s from %s", MODULE_NAME, dest_dir)
    try:
        if dest_root.is_dir():
            shutil.rmtree(dest_root)
        elif dest_root.exists():
            dest_root.unlink()
        if dest_mod.exists() or dest_mod.is_symlink():
            dest_mod.unlink()
    except OSError as exc:
        raise ModuleError(
            f"Failed to uninstall {MODULE_NAME} from {dest_dir}: {exc}"
        ) from exc
    if removed:
        log.debug("Removed %s and %s", dest_root, dest_mod)
    else:
        log.debug("Nothing to remove at %s", dest_dir)
    return PackageUninstallResult(path=dest_mod, root=dest_root, removed=removed)


def _default_uv_pip_cmd(spec: str, target: Path) -> list[str]:
    return [
        find_uv(),
        "pip",
        "install",
        "--python",
        sys.executable,
        "--target",
        str(target),
        spec,
    ]


def _direct_url_path(dist: object) -> Path | None:
    """Return a local project path from ``direct_url.json``, if present.

    Args:
        dist: An ``importlib.metadata`` distribution.

    Returns:
        Resolved project directory, or ``None``.
    """
    read_text = getattr(dist, "read_text", None)
    if read_text is None:
        return None
    try:
        raw = read_text("direct_url.json")
    except (FileNotFoundError, OSError):
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    url = data.get("url")
    if not isinstance(url, str) or not url.startswith("file:"):
        return None
    parsed = urlparse(url)
    path = Path(url2pathname(unquote(parsed.path)))
    if path.is_dir():
        return path.resolve()
    return None
