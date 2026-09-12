"""Maya runtime library for game-development tools.

Visual effects is out of scope. This package does not import the CLI.

Attributes:
    __version__: Installed package version, or ``0.0.0`` if metadata is missing.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mtmaya")
except PackageNotFoundError:
    __version__ = "0.0.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["__version__"]
