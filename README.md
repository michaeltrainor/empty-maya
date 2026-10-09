# mtmaya

Library and CLI for Autodesk Maya tools, focused on game development. Visual effects is out of scope. macOS first; Windows 11 later.

This repo is a uv workspace with two packages: `mtmaya` (Maya runtime) and `mtmaya-cli` (the `mtm` console script). `mtmaya` depends on `mtqt` from `C:\Users\micha\dev\python\empty-qt`. `mtmaya.core.ui` wraps Maya UI as Qt objects and builds menus and shelves. `import mtmaya` does not load the CLI, Qt, or `mtmaya.core`.

## Requirements

- Autodesk Maya 2027 or later (Python 3.13)
- [uv](https://docs.astral.sh/uv/)
- macOS (this checkout)

Maya ships `mayapy`. uv and `venv` need an executable named `python` in the same directory. Create that symlink once per Maya install:

```bash
./scripts/macos/link-mayapy.sh
# optional: ./scripts/macos/link-mayapy.sh 2028
# optional: ./scripts/macos/link-mayapy.sh --dry-run
```

The script prints `UV_PYTHON`. Point uv at that interpreter so it does not use a managed CPython 3.13 that cannot `import maya`:

```bash
export UV_PYTHON="/Applications/Autodesk/maya2027/Maya.app/Contents/bin/python"
uv venv --python "$UV_PYTHON"
uv sync
```

Do not add Maya's `bin/` to `PATH`. Do not install PyPI `PySide6` (Maya already ships it). Do not install packages into Maya's system `site-packages`.

Default `pytest` does not import Maya and must pass without launching Maya. Tests that need `maya.standalone` use `@pytest.mark.maya` and are skipped when Maya is missing. Never run those from a git hook; `maya.standalone.initialize()` checks out a license.

PySide6 widget tests use the `qtbot` fixture from pytest-qt in this dev environment. They must not launch Maya or construct a `QApplication`. `@pytest.mark.maya` tests must not use `qtbot`. The dev environment installs PySide6 because `mtqt` requires it. `mtm install` still strips PySide6 out of the Maya module tree.

## Install into Maya

`mtm install` scaffolds the stock Maya module folders (same as `mtm module new`), writes `scripts/userSetup.py`, and installs the `mtmaya` runtime graph into `python/` with `uv pip install --target`. CLI deps (typer, jinja2) stay out of that tree. Default destination is `$MAYA_APP_DIR/2027/modules` (`--maya-version` / `--maya-app-dir` override). `mtm uninstall` removes that module only.

```bash
uv run mtm install
uv run mtm install --maya-version 2028
uv run mtm uninstall
```

## Maya modules

`mtm module new NAME` writes a relocatable source tree: `NAME/NAME.mod` (`ModulePath` `.`) plus `scripts/`, `plug-ins/`, `icons/`, and `presets/`. `mtm module install` copies that tree to `$MAYA_APP_DIR/{year}/modules/{name}/` and writes a sibling `{name}.mod` with a relative `ModulePath`. Use `--target` to pick the destination directory and `--dry-run` to print the plan without writing. Default pytest still does not launch Maya.

```bash
uv run mtm module new demo
uv run mtm module install --dry-run
uv run mtm module install --maya-version 2029
```

`mtm -v` / `--verbose` logs INFO diagnostics to stderr; `--debug` logs DEBUG; `-q` / `--quiet` logs only errors. Command results still go to stdout. Default is warnings-only.

## Development

```bash
uv sync
uv run mtm --help
uv run mtm version
uv run mtm install --help
uv run mtm module --help
uv run ruff check .
uv run ruff format .
uv run pytest
uv run pre-commit install
uv run pre-commit run --all-files
uv run mkdocs serve
uv run mkdocs build
```

## Docs

Library code in `packages/` uses Google-style docstrings. MkDocs Material and mkdocstrings render them locally (`uv run mkdocs serve`). Tests are not documented.

Git identity for this repo is local (`mtd3v` / `accounts@michaeltrainor.com`). Do not set global git config.

After a session that changes code: ruff, pytest, pre-commit, then push the pull request branch. Planned work opens a PR against `main`. Small on-the-fly changes get a branch and PR automatically. The remote is Cursor Origin (`origin.cursor.com`), not GitHub.
