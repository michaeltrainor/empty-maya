"""CLI command groups for mtm."""

from __future__ import annotations

import typer


def register(root: typer.Typer) -> None:
    """Attach subcommand groups to the root Typer app.

    Args:
        root: Root ``mtm`` Typer application.
    """
    from mtmaya_cli.commands.install import register as register_install
    from mtmaya_cli.commands.module import app as module_app

    root.add_typer(module_app, name="module")
    register_install(root)
