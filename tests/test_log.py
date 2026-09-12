import logging

import pytest

from mtmaya.log import PACKAGE_LOGGER_NAME, coerce_level, configure, level_from_flags


def test_package_logger_has_null_handler() -> None:
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    assert any(isinstance(handler, logging.NullHandler) for handler in logger.handlers)


def test_configure_sets_level() -> None:
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    configure(level="DEBUG")
    assert logger.level == logging.DEBUG
    configure(level=logging.INFO)
    assert logger.level == logging.INFO


def test_configure_does_not_duplicate_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure(level="INFO")
    configure(level="INFO")
    logging.getLogger(PACKAGE_LOGGER_NAME).info("once")
    captured = capsys.readouterr()
    assert captured.err.count("once") == 1


def test_configure_unknown_level_raises() -> None:
    with pytest.raises(ValueError, match="Unknown log level"):
        configure(level="not-a-level")


def test_coerce_level_accepts_name_and_int() -> None:
    assert coerce_level("info") == logging.INFO
    assert coerce_level(logging.WARNING) == logging.WARNING


@pytest.mark.parametrize(
    ("verbose", "debug", "quiet", "expected"),
    [
        (False, False, False, logging.WARNING),
        (True, False, False, logging.INFO),
        (False, True, False, logging.DEBUG),
        (True, True, False, logging.DEBUG),
        (True, True, True, logging.ERROR),
        (False, False, True, logging.ERROR),
    ],
)
def test_level_from_flags(
    verbose: bool, debug: bool, quiet: bool, expected: int
) -> None:
    assert level_from_flags(verbose=verbose, debug=debug, quiet=quiet) == expected
