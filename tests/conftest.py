"""Pytest configuration. Maya tests stay opt-in and do not grab a license by default."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    _ = config
    try:
        import maya  # noqa: F401
    except ImportError:
        skip_maya = pytest.mark.skip(reason="Maya is not available in this interpreter")
        for item in items:
            if item.get_closest_marker("maya"):
                item.add_marker(skip_maya)


@pytest.fixture(autouse=True)
def _reset_mtmaya_logging() -> Iterator[None]:
    saved: list[tuple[logging.Logger, list[logging.Handler], int, bool]] = []
    for name in ("mtmaya", "mtmaya_qt", "mtmaya_cli"):
        logger = logging.getLogger(name)
        saved.append((logger, list(logger.handlers), logger.level, logger.propagate))
    yield
    for logger, handlers, level, propagate in saved:
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = propagate
