"""Verify the Maya debug environment contains debugpy and not PySide6."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _inside(child: Path, parent: Path) -> bool:
    """Return whether ``child`` is ``parent`` or a path under it."""
    child_s = os.path.normcase(os.path.abspath(child))
    parent_s = os.path.normcase(os.path.abspath(parent)).rstrip("\\/")
    return child_s == parent_s or child_s.startswith(parent_s + os.sep)


def main() -> int:
    """Exit 0 when debugpy is inside ``.venv.maya`` and PySide6 is not.

    Reads ``MTMAYA_VENV_DIR`` and ``MTMAYA_MAYA_BIN`` from the environment.
    The caller must run this file with ``.venv.maya``'s interpreter.

    Returns:
        Process status. ``0`` when the environment matches the debug layout.
    """
    root = Path(os.environ["MTMAYA_VENV_DIR"]).absolute()
    maya_bin = Path(os.environ["MTMAYA_MAYA_BIN"]).absolute()
    maya_root = maya_bin.parent

    import debugpy

    # absolute() keeps a uv cache symlink counted under .venv.maya.
    location = Path(debugpy.__file__).absolute()
    base = Path(sys.base_prefix).absolute()
    if not _inside(location, root):
        print(f"error: debugpy is outside .venv.maya: {location}", file=sys.stderr)
        return 1
    if _inside(location, maya_root):
        print(f"error: debugpy is inside Maya: {location}", file=sys.stderr)
        return 1
    if not _inside(base, maya_root):
        print(f"error: interpreter base is not Maya: {base}", file=sys.stderr)
        return 1
    if _inside(base, root):
        print(f"error: interpreter base is .venv.maya: {base}", file=sys.stderr)
        return 1

    spec = importlib.util.find_spec("PySide6")
    origin = None if spec is None else spec.origin
    if origin is not None and _inside(Path(origin), root):
        print(f"error: PySide6 is installed in .venv.maya: {origin}", file=sys.stderr)
        return 1

    print(f"debugpy {debugpy.__version__}")
    print(f"base {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
