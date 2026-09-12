"""``mtm module install`` — copy a module tree into Maya prefs."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mtmaya_cli.commands.module.app import app, exit_on_module_error
from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.install import find_mod_file
from mtmaya_cli.module.install import install_module as copy_install
from mtmaya_cli.module.modfile import parse_modfile
from mtmaya_cli.module.paths import DEFAULT_MAYA_VERSION, user_modules_dir

_CWD = Path(".")


@app.command("install")
def install_module(
    path: Annotated[
        Path,
        typer.Argument(
            help="Module root directory. Defaults to the current directory."
        ),
    ] = _CWD,
    target: Annotated[
        Path | None,
        typer.Option(
            "--target",
            help="Directory for {name}/ and {name}.mod. Default: "
            "$MAYA_APP_DIR/{maya_version}/modules.",
        ),
    ] = None,
    maya_version: Annotated[
        str | None,
        typer.Option(
            "--maya-version",
            help="Maya year for MAYAVERSION and the prefs subdirectory. "
            "Default: from .mod or 2027.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the install plan without writing."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing installed module."),
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
    """Install a module by copying its tree and writing a sibling .mod.

    Copies the source tree to ``$MAYA_APP_DIR/{maya_version}/modules/{name}/``
    unless ``--target`` is set. The live ``.mod`` sits next to that folder
    with a relative ModulePath. Prompts when ``--interactive`` is passed.

    Args:
        path: Module root directory.
        target: Directory for the copied tree and sibling .mod, or None for
            the versioned user modules dir.
        maya_version: Maya year for MAYAVERSION and the prefs subdirectory
            when target is omitted.
        dry_run: Print the install plan without writing.
        force: Overwrite an existing installed module.
        interactive: Prompt for values, showing defaults.
    """
    if interactive:
        path, target, maya_version, dry_run, force = _prompt_install_options(
            path=path,
            target=target,
            maya_version=maya_version,
            dry_run=dry_run,
            force=force,
        )
    try:
        result = copy_install(
            path,
            target=target,
            dry_run=dry_run,
            force=force,
            maya_version=maya_version,
        )
    except ModuleError as exc:
        exit_on_module_error(exc)
    if result.written:
        typer.echo(f"Copied {result.root}")
        typer.echo(f"Wrote {result.path}")
        return
    typer.echo(f"Would copy {path.resolve()} -> {result.root}")
    typer.echo(f"Would write {result.path}")
    typer.echo(result.contents, nl=False)


def _prompt_install_options(
    *,
    path: Path,
    target: Path | None,
    maya_version: str | None,
    dry_run: bool,
    force: bool,
) -> tuple[Path, Path | None, str | None, bool, bool]:
    """Collect ``mtm module install`` arguments with defaults shown.

    Args:
        path: Module root default.
        target: Install directory already passed, if any.
        maya_version: Maya year override already passed, if any.
        dry_run: Dry-run default.
        force: Overwrite default.

    Returns:
        Values to pass to ``install_module``.
    """
    path = Path(
        typer.prompt("Module path", default=str(path.expanduser().resolve()))
    ).expanduser()
    detected = _maya_version_from_source(path)
    version_default = maya_version or detected
    maya_version = typer.prompt("Maya version", default=version_default)
    if target is not None:
        target_default = target.expanduser().resolve()
    else:
        target_default = user_modules_dir(maya_version=maya_version)
    target = Path(
        typer.prompt("Target directory", default=str(target_default))
    ).expanduser()
    dry_run = typer.confirm("Dry run", default=dry_run)
    existing = _existing_install(path, target)
    if existing is not None and not force:
        force = typer.confirm("Destination already exists. Overwrite", default=False)
    return path, target, maya_version, dry_run, force


def _maya_version_from_source(source: Path) -> str:
    """Return ``MAYAVERSION`` from the source ``.mod``, or ``2027``.

    Args:
        source: Module root directory.

    Returns:
        Maya year string.
    """
    try:
        mod_file = find_mod_file(source.resolve())
        return parse_modfile(mod_file.read_text(encoding="utf-8")).maya_version
    except (ModuleError, OSError):
        return DEFAULT_MAYA_VERSION


def _existing_install(source: Path, dest_dir: Path) -> Path | None:
    """Return the existing dest ``.mod`` or tree path, if either is present.

    Args:
        source: Module root directory.
        dest_dir: Directory that will hold ``{name}/`` and ``{name}.mod``.

    Returns:
        Existing destination path, or ``None`` if the source is unreadable or
        nothing is installed yet.
    """
    try:
        mod_file = find_mod_file(source.resolve())
        specifier = parse_modfile(mod_file.read_text(encoding="utf-8"))
    except (ModuleError, OSError):
        return None
    dest_mod = dest_dir / f"{specifier.name}.mod"
    dest_root = dest_dir / specifier.name
    if dest_mod.exists():
        return dest_mod
    if dest_root.exists():
        return dest_root
    return None
