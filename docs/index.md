# mtmaya

Library and CLI for Autodesk Maya tools, focused on game development. Visual effects is out of scope. macOS first; Windows 11 later.

The Maya import package is `mtmaya`. Shared Qt widgets are `mtmaya_qt`. The installed command is `mtm` (`mtmaya-cli`).

## Local docs

```bash
uv run mkdocs serve
uv run mkdocs build
```

Google-style docstrings in `packages/` are rendered on the [API reference](reference.md) page.

## Install into Maya

`mtm install` scaffolds a full Maya module and installs the `mtmaya` runtime graph into `python/` with `uv pip install --target`. `mtm uninstall` removes it. See the repository README for flags and examples.

## Maya modules

`mtm module new NAME` scaffolds a relocatable source tree (`NAME/NAME.mod` with `ModulePath` `.`). `mtm module install` copies it to `$MAYA_APP_DIR/{year}/modules/{name}/` and writes a sibling `{name}.mod`. `--target` picks the destination; `--dry-run` prints the plan without writing. See the repository README for examples.

`mtm -v` / `--verbose` logs INFO diagnostics to stderr; `--debug` logs DEBUG; `-q` / `--quiet` logs only errors. Command results still go to stdout.

## Development

See the repository README for Maya interpreter setup, `uv sync`, ruff, pytest, and pre-commit. Default pytest does not import Maya.
