from pathlib import Path

from typer.testing import CliRunner

from mtmaya_cli import app

runner = CliRunner()


def test_new_file_tree(tmp_path: Path) -> None:
    result = runner.invoke(app, ["module", "new", "demo", "--directory", str(tmp_path)])
    assert result.exit_code == 0, result.output
    root = tmp_path / "demo"
    assert (root / "demo.mod").is_file()
    for name in ("scripts", "plug-ins", "icons", "presets"):
        assert (root / name).is_dir()
    text = (root / "demo.mod").read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert "Created " in result.stdout
    assert not (root / "scripts" / "userSetup.py").exists()


def test_new_verbose_emits_info(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["-v", "module", "new", "demo", "--directory", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "Created " in result.stdout
    assert "Creating module" in result.stderr


def test_new_default_is_quiet_except_echo(tmp_path: Path) -> None:
    result = runner.invoke(app, ["module", "new", "demo", "--directory", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Created " in result.stdout
    assert "Creating module" not in result.stdout
    assert "Creating module" not in result.stderr


def test_new_with_plugin(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["module", "new", "demo", "--directory", str(tmp_path), "--with-plugin"],
    )
    assert result.exit_code == 0, result.output
    plugin = tmp_path / "demo" / "plug-ins" / "demo.py"
    text = plugin.read_text(encoding="utf-8")
    assert "maya_useNewAPI = True" in text
    assert "initializePlugin" in text
    assert "uninitializePlugin" in text


def test_new_with_user_setup(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["module", "new", "demo", "--directory", str(tmp_path), "--with-user-setup"],
    )
    assert result.exit_code == 0, result.output
    setup = tmp_path / "demo" / "scripts" / "userSetup.py"
    text = setup.read_text(encoding="utf-8")
    assert "demo" in text
    assert "maya.cmds" not in text
    assert "import maya" not in text


def test_new_force(tmp_path: Path) -> None:
    args = ["module", "new", "demo", "--directory", str(tmp_path)]
    assert runner.invoke(app, args).exit_code == 0
    denied = runner.invoke(app, args)
    assert denied.exit_code != 0
    assert "already exists" in denied.output
    forced = runner.invoke(app, [*args, "--force"])
    assert forced.exit_code == 0, forced.output


def test_new_invalid_name(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["module", "new", "has space", "--directory", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "spaces" in result.output


def test_new_interactive_without_name(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["module", "new", "--directory", str(tmp_path)],
        input="demo\n\n\n\n\n\n",
    )
    assert result.exit_code == 0, result.output
    root = tmp_path / "demo"
    assert (root / "demo.mod").is_file()
    assert not (root / "scripts" / "userSetup.py").exists()
    assert not (root / "plug-ins" / "demo.py").exists()
    assert "Created " in result.stdout


def test_new_interactive_flag_accepts_defaults(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["module", "new", "demo", "--directory", str(tmp_path), "--interactive"],
        input="\n\n\n\n\n\n",
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "demo" / "demo.mod").is_file()


def test_new_interactive_with_user_setup(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["module", "new", "--directory", str(tmp_path)],
        input="demo\n\n\n\nn\ny\n",
    )
    assert result.exit_code == 0, result.output
    setup = tmp_path / "demo" / "scripts" / "userSetup.py"
    assert setup.is_file()
    assert "maya.cmds" not in setup.read_text(encoding="utf-8")
