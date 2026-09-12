"""Maya module CLI group.

Command modules are imported for their Typer registration side effects.
"""

from mtmaya_cli.commands.module import install as install  # noqa: F401
from mtmaya_cli.commands.module import new as new  # noqa: F401
from mtmaya_cli.commands.module.app import app

__all__ = ["app"]
