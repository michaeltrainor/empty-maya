import importlib.util
import sys
from importlib.metadata import requires


def test_mtmaya_does_not_import_cli() -> None:
    # Popping the parent leaves mtmaya_cli.module cached. A later import
    # then builds a new parent that does not get that child bound, and
    # monkeypatch can no longer resolve mtmaya_cli.module.package.
    saved = {
        name: sys.modules[name]
        for name in ("mtmaya_cli", "mtqt")
        if name in sys.modules
    }
    sys.modules.pop("mtmaya_cli", None)
    sys.modules.pop("mtqt", None)
    try:
        import mtmaya

        assert "mtmaya_cli" not in sys.modules
        assert "mtqt" not in sys.modules
        assert importlib.util.find_spec("mtmaya.cli") is None
        assert importlib.util.find_spec("mtmaya.qt") is None
        assert not hasattr(mtmaya, "cli")
    finally:
        sys.modules.update(saved)


def test_mtmaya_requires_exclude_cli_libs() -> None:
    reqs = requires("mtmaya") or []
    joined = "\n".join(reqs).lower()
    assert "typer" not in joined
    assert "jinja2" not in joined
    assert "jinja" not in joined
    assert "pyside6" not in joined
    assert "mtmaya-cli" not in joined
    assert "mtmaya-qt" not in joined
    assert "debugpy" not in joined
    assert "mtqt" in joined
