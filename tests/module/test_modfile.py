from pathlib import Path

import pytest

from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.modfile import parse_modfile, render_modfile, resolve_module_path


def test_render_modfile_has_no_blank_line_after_specifier() -> None:
    text = render_modfile(
        name="demo",
        version="0.1.0",
        maya_version="2027",
        module_path=".",
        platform="mac",
    )
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert text.count("\n") == 1
    assert text.startswith("+ MAYAVERSION:2027 PLATFORM:mac demo 0.1.0 .")


def test_parse_and_resolve_relative_module_path(tmp_path: Path) -> None:
    mod_file = tmp_path / "demo.mod"
    mod_file.write_text(
        render_modfile(
            name="demo",
            version="1.2.3",
            maya_version="2027",
            module_path=".",
        ),
        encoding="utf-8",
    )
    specifier = parse_modfile(mod_file.read_text(encoding="utf-8"))
    assert specifier.name == "demo"
    assert specifier.version == "1.2.3"
    assert specifier.maya_version == "2027"
    assert specifier.module_path == "."
    assert resolve_module_path(specifier, mod_file) == tmp_path.resolve()


def test_parse_modfile_missing_specifier() -> None:
    with pytest.raises(ModuleError, match="No module specifier"):
        parse_modfile("# just a comment\n")


def test_render_modfile_extra_lines_have_no_blank_line() -> None:
    text = render_modfile(
        name="demo",
        version="0.1.0",
        maya_version="2027",
        module_path=".",
        extra_lines=("PYTHONPATH +:= python", "", "  MAYA_SCRIPT_PATH +:= scripts  "),
        platform="mac",
    )
    assert text.endswith("\n")
    assert "\n\n" not in text
    assert text.splitlines() == [
        "+ MAYAVERSION:2027 PLATFORM:mac demo 0.1.0 .",
        "PYTHONPATH +:= python",
        "MAYA_SCRIPT_PATH +:= scripts",
    ]


def test_render_modfile_windows_path_and_host_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mtmaya_cli.module.paths.sys.platform", "win32")
    text = render_modfile(
        name="mtmaya",
        version="0.1.0",
        maya_version="2027",
        module_path=r"C:\Users\micha\dev\autodesk\maya\2027\modules\mtmaya",
        extra_lines=("PYTHONPATH +:= python",),
    )
    assert text.splitlines() == [
        "+ MAYAVERSION:2027 PLATFORM:win64 mtmaya 0.1.0 "
        "C:/Users/micha/dev/autodesk/maya/2027/modules/mtmaya",
        "PYTHONPATH +:= python",
    ]


def test_platform_round_trip() -> None:
    text = render_modfile(
        name="demo",
        version="0.1.0",
        maya_version="2027",
        module_path=".",
        platform="win64",
    )
    assert "PLATFORM:win64" in text
    specifier = parse_modfile(text)
    assert specifier.platform == "win64"
    again = render_modfile(
        name=specifier.name,
        version=specifier.version,
        maya_version=specifier.maya_version,
        module_path=specifier.module_path,
        platform=specifier.platform,
    )
    assert again == text
