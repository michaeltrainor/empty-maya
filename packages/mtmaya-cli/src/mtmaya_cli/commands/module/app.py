"""Typer application for ``mtm module``."""

from __future__ import annotations

import logging
from typing import NoReturn

import typer

from mtmaya_cli.module import ModuleError

app = typer.Typer(
    name="module",
    help="Scaffold and install Maya module (.mod) trees.",
    no_args_is_help=True,
)

log = logging.getLogger(__name__)


def exit_on_module_error(exc: ModuleError) -> NoReturn:
    """Print a domain error and abort the CLI.

    Args:
        exc: Error from ``mtmaya_cli.module``.
    """
    log.debug("ModuleError", exc_info=exc)
    typer.echo(str(exc), err=True)
    raise typer.Exit(1) from exc
