"""Command-line interface for mtmaya."""

from __future__ import annotations

from typing import Annotated

import typer

from mtmaya import __version__
from mtmaya.log import PACKAGE_LOGGER_NAME, configure, level_from_flags
from mtmaya_cli.commands import register

app = typer.Typer(
    name="mtm",
    help="Tools for Autodesk Maya, focused on game development.",
    no_args_is_help=True,
)
register(app)


@app.callback()
def main(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Log INFO diagnostics to stderr.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Log DEBUG diagnostics to stderr."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Log only errors to stderr.",
        ),
    ] = False,
) -> None:
    """Tools for Autodesk Maya, focused on game development."""
    configure(
        level=level_from_flags(verbose=verbose, debug=debug, quiet=quiet),
        names=(PACKAGE_LOGGER_NAME, "mtmaya_qt", "mtmaya_cli"),
    )


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)
