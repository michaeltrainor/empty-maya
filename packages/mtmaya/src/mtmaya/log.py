"""Package logging for mtmaya.

Library modules emit via ``logging.getLogger(__name__)``. They do not add
handlers or call :func:`configure`. The CLI (or a future Maya
``userSetup.py``) calls :func:`configure` at startup.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

PACKAGE_LOGGER_NAME = "mtmaya"
_FORMAT = "%(levelname)s %(name)s: %(message)s"


def coerce_level(level: int | str) -> int:
    """Return a numeric logging level.

    Args:
        level: A ``logging`` level int, or a name such as ``"INFO"``.

    Returns:
        Numeric level suitable for ``logger.setLevel``.

    Raises:
        ValueError: If ``level`` is an unknown level name.
    """
    if isinstance(level, int):
        return level
    mapping = logging.getLevelNamesMapping()
    try:
        return mapping[level.upper()]
    except KeyError:
        raise ValueError(f"Unknown log level: {level}") from None


def level_from_flags(
    *,
    verbose: bool = False,
    debug: bool = False,
    quiet: bool = False,
) -> int:
    """Map CLI verbosity flags to a logging level.

    Quiet wins, then debug, then verbose. With none set the default is
    ``WARNING`` so the CLI stays quiet except for ``typer.echo`` output.

    Args:
        verbose: If true (and not quiet/debug), use ``INFO``.
        debug: If true (and not quiet), use ``DEBUG``.
        quiet: If true, use ``ERROR``.

    Returns:
        ``logging`` level int.
    """
    if quiet:
        return logging.ERROR
    if debug:
        return logging.DEBUG
    if verbose:
        return logging.INFO
    return logging.WARNING


def configure(
    *,
    level: int | str = logging.WARNING,
    handler: logging.Handler | None = None,
    names: Sequence[str] = (PACKAGE_LOGGER_NAME,),
) -> None:
    """Configure package loggers.

    Library code does not call this. The CLI (or a future Maya
    ``userSetup.py``) does. Pass ``handler`` to replace the default stderr
    ``StreamHandler`` (for example a Maya script-editor handler).

    Safe to call more than once (tests, nested CLI invocations). Existing
    non-``NullHandler`` handlers on each named logger are replaced.

    Args:
        level: Logging level as an ``int`` or name (``"INFO"``). Default
            is ``WARNING``.
        handler: Handler to attach. ``None`` uses a stderr stream handler.
            The same handler instance is attached to every name.
        names: Logger names to configure. Default is ``mtmaya``.

    Raises:
        ValueError: If ``level`` is an unknown level name.
    """
    numeric = coerce_level(level)
    if handler is None:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
    for name in names:
        logger = logging.getLogger(name)
        logger.setLevel(numeric)
        for existing in list(logger.handlers):
            if not isinstance(existing, logging.NullHandler):
                logger.removeHandler(existing)
        logger.addHandler(handler)
        logger.propagate = False
