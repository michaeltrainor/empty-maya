"""``mtm module new`` — scaffold a relocatable Maya module tree."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mtmaya_cli.commands.module.app import app, exit_on_module_error
from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.paths import DEFAULT_MAYA_VERSION
from mtmaya_cli.module.scaffold import create_module

_CWD = Path(".")


@app.command("new")
def new_module(
    name: Annotated[
        str | None,
        typer.Argument(help="Module name (no spaces). Prompted if omitted."),
    ] = None,
    directory: Annotated[
        Path,
        typer.Option("--directory", help="Parent directory for the new module tree."),
    ] = _CWD,
    version: Annotated[
        str,
        typer.Option("--version", help="Module version."),
    ] = "0.1.0",
    maya_version: Annotated[
        str,
        typer.Option("--maya-version", help="Maya year for MAYAVERSION."),
    ] = DEFAULT_MAYA_VERSION,
    with_plugin: Annotated[
        bool,
        typer.Option(
            "--with-plugin",
            help="Write a Python plug-in stub under plug-ins/.",
        ),
    ] = False,
    with_user_setup: Annotated[
        bool,
        typer.Option(
            "--with-user-setup",
            help="Write scripts/userSetup.py (Maya init stub).",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite generated files; remove leftover plugin/"
            "userSetup stubs not requested this time.",
        ),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Prompt for values, showing defaults.",
        ),
    ] = False,
) -> None:
    """Create a relocatable Maya module source tree.

    Writes NAME/ with NAME.mod and the default Maya module folders. Prompts
    for values when NAME is omitted or ``--interactive`` is passed. Does not
    touch Maya preferences; use ``mtm module install`` to copy the tree.

    Args:
        name: Module name (no spaces). Prompted if omitted.
        directory: Parent directory for the new module tree.
        version: Module version written into the .mod file.
        maya_version: Maya year for MAYAVERSION.
        with_plugin: Write a Python plug-in stub under plug-ins/.
        with_user_setup: Write scripts/userSetup.py.
        force: Overwrite generated files; remove leftover stubs not requested.
        interactive: Prompt for values, showing defaults.
    """
    if interactive or name is None:
        name, directory, version, maya_version, with_plugin, with_user_setup, force = (
            _prompt_new_options(
                name=name,
                directory=directory,
                version=version,
                maya_version=maya_version,
                with_plugin=with_plugin,
                with_user_setup=with_user_setup,
                force=force,
            )
        )
    try:
        root = create_module(
            name,
            directory=directory,
            version=version,
            maya_version=maya_version,
            with_plugin=with_plugin,
            with_user_setup=with_user_setup,
            force=force,
        )
    except ModuleError as exc:
        exit_on_module_error(exc)
    typer.echo(f"Created {root}")


def _prompt_new_options(
    *,
    name: str | None,
    directory: Path,
    version: str,
    maya_version: str,
    with_plugin: bool,
    with_user_setup: bool,
    force: bool,
) -> tuple[str, Path, str, str, bool, bool, bool]:
    """Collect ``mtm module new`` arguments with defaults shown.

    Args:
        name: Module name already passed, if any.
        directory: Parent directory default.
        version: Module version default.
        maya_version: Maya year default.
        with_plugin: Plug-in stub default.
        with_user_setup: userSetup.py stub default.
        force: Overwrite default.

    Returns:
        Values to pass to ``create_module``.
    """
    if name:
        name = typer.prompt("Module name", default=name)
    else:
        name = typer.prompt("Module name")
    directory = Path(
        typer.prompt("Directory", default=str(directory.expanduser().resolve()))
    ).expanduser()
    version = typer.prompt("Version", default=version)
    maya_version = typer.prompt("Maya version", default=maya_version)
    with_plugin = typer.confirm("With plugin", default=with_plugin)
    with_user_setup = typer.confirm("With userSetup.py", default=with_user_setup)
    dest = directory / name
    if dest.exists() and not force:
        force = typer.confirm("Destination exists. Overwrite", default=False)
    return name, directory, version, maya_version, with_plugin, with_user_setup, force
