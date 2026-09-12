import importlib.util
import sys
from importlib.metadata import requires


def test_mtmaya_does_not_import_cli() -> None:
    sys.modules.pop("mtmaya_cli", None)
    import mtmaya

    assert "mtmaya_cli" not in sys.modules
    assert importlib.util.find_spec("mtmaya.cli") is None
    assert not hasattr(mtmaya, "cli")


def test_mtmaya_requires_exclude_cli_libs() -> None:
    reqs = requires("mtmaya") or []
    joined = "\n".join(reqs).lower()
    assert "typer" not in joined
    assert "jinja2" not in joined
    assert "jinja" not in joined
    assert "pyside6" not in joined
    assert "mtmaya-cli" not in joined
