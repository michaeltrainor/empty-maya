"""``mtm install`` / ``mtm uninstall`` — Maya module for this package."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mtmaya_cli.commands.module.app import exit_on_module_error
from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.package import install_package, uninstall_package
from mtmaya_cli.module.paths import DEFAULT_MAYA_VERSION


def install(
    maya_version: Annotated[
        str,
        typer.Option("--maya-version", help="Maya year subdirectory. Default: 2027."),
    ] = DEFAULT_MAYA_VERSION,
    maya_app_dir: Annotated[
        Path | None,
        typer.Option(
            "--maya-app-dir",
            help="Maya application directory. Default: $MAYA_APP_DIR or the "
            "platform default.",
        ),
    ] = None,
) -> None:
    """Install mtmaya as a Maya module.

    Scaffolds the stock module folders (scripts, plug-ins, icons, presets)
    with ``scripts/userSetup.py``, installs the ``mtmaya`` runtime graph
    into ``python/`` with ``uv pip install --target``, and writes a
    sibling ``mtmaya.mod``. Replaces an existing install.

    Args:
        maya_version: Maya year subdirectory, e.g. ``2027``.
        maya_app_dir: Override for ``MAYA_APP_DIR``.
    """
    try:
        result = install_package(maya_version=maya_version, app_dir=maya_app_dir)
    except ModuleError as exc:
        exit_on_module_error(exc)
    typer.echo(f"Installed {result.root}")
    typer.echo(f"Wrote {result.path}")


def uninstall(
    maya_version: Annotated[
        str,
        typer.Option("--maya-version", help="Maya year subdirectory. Default: 2027."),
    ] = DEFAULT_MAYA_VERSION,
    maya_app_dir: Annotated[
        Path | None,
        typer.Option(
            "--maya-app-dir",
            help="Maya application directory. Default: $MAYA_APP_DIR or the "
            "platform default.",
        ),
    ] = None,
) -> None:
    """Remove the installed mtmaya Maya module.

    Deletes ``mtmaya/`` and ``mtmaya.mod`` under the versioned modules
    directory. Exits 0 if nothing is installed.

    Args:
        maya_version: Maya year subdirectory, e.g. ``2027``.
        maya_app_dir: Override for ``MAYA_APP_DIR``.
    """
    try:
        result = uninstall_package(maya_version=maya_version, app_dir=maya_app_dir)
    except ModuleError as exc:
        exit_on_module_error(exc)
    if result.removed:
        typer.echo(f"Removed {result.root}")
        typer.echo(f"Removed {result.path}")
        return
    typer.echo(f"mtmaya is not installed at {result.path.parent}")


def register(root: typer.Typer) -> None:
    """Attach ``install`` and ``uninstall`` to the root Typer app.

    Args:
        root: Root ``mtm`` Typer application.
    """
    root.command("install")(install)
    root.command("uninstall")(uninstall)
