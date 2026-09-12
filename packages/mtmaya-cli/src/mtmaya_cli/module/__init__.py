"""Maya ``.mod`` paths, scaffolding, and copy installs.

This package does not import ``maya``.
"""

from __future__ import annotations


class ModuleError(Exception):
    """Raised when a Maya module operation fails."""
