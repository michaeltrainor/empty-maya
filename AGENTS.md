# mtmaya

## uv

- Use **uv** to manage this project: venv, lockfile, deps, and running tools.
- Prefer `uv sync`, `uv add` / `uv remove`, and `uv run …` over pip, poetry, or bare `python`/`pytest`/`ruff`.
- Create the venv with `uv venv` (and `UV_PYTHON` per Maya rules); do not use `python -m venv` or install packages with `pip` into the project env.

## Maya / Python

- Target Maya 2027+ (CPython 3.13). The venv interpreter is Maya's `python` symlink next to `mayapy`, not uv-managed CPython.
- Create the symlink with `scripts/windows/link-mayapy.ps1` on Windows or `scripts/macos/link-mayapy.sh` on macOS. Set `UV_PYTHON` to that path before `uv venv` / `uv sync`.
- Do not put Maya's `bin/` on `PATH`. Do not add PyPI `PySide6`. Do not install into Maya's `site-packages`. Do not use PyMel.
- Prefer `maya.cmds` for tools; OpenMaya 2.0 only when cmds is not enough.
- Default pytest must not import `maya` or call `maya.standalone.initialize()` (license checkout). Gate Maya tests with `@pytest.mark.maya`.

## Package boundaries

`mtmaya` ships into Maya. `mtmaya-cli` does not.

- `packages/mtmaya` must not import `mtmaya_cli`, Typer, or Jinja.
- `packages/mtmaya-cli` must not import `maya` or call `maya.standalone.initialize()`.
- Add a runtime dependency only when code that runs inside Maya needs it. CLI-only libraries stay on `mtmaya-cli`.
- `mtmaya` depends on `mtqt` for shared Qt widgets. `import mtmaya` must not import `mtqt` or `mtmaya.core`.
- Keep public imports explicit. Do not re-export optional subsystems (Qt, modules) from `import mtmaya`.

## Filesystem and install

- Use `pathlib.Path`. Pass `environ` into library code instead of reading `os.environ` there.
- Install and uninstall only touch the module tree and its sibling `.mod`. Refuse a destination that resolves to the source tree or to Maya’s install directory.
- Support `dry_run` on anything that writes or deletes. Overwrite only when `force` is set.
- Skip VCS, caches, and virtualenvs when copying (see `_COPY_IGNORE_NAMES` in `mtmaya_cli.module.install`).
- Library path code must stay valid on Windows. Keep shell scripts under `scripts/macos/` or `scripts/windows/`.

## Errors, logging, and CLI output

- Expected failures raise a domain error (`ModuleError` or a sibling). Catch it at the Typer command and exit with one sentence.
- Libraries log with `logging.getLogger(__name__)`. They do not add handlers or call `configure`.
- User-facing results go to stdout via `typer.echo`. Diagnostics go to stderr through the `mtmaya` logger.
- Default level stays `WARNING`. `INFO` and `DEBUG` only when `-v` or `--debug` is set.

```python
log = logging.getLogger(__name__)

try:
    result = install_module(source, dry_run=dry_run)
except ModuleError as exc:
    exit_on_module_error(exc)
typer.echo(f"Installed {result.root}")
```

## Public API

- Type public functions. Prefer `Path`, `Mapping`, and frozen `slots=True` dataclasses for results.
- Keep `__all__` limited to what another tool should call.
- One function does one job: resolve paths, render a `.mod`, copy a tree, and print a result stay separate.
- Match existing style: `from __future__ import annotations`, Google docstrings on public `packages/` APIs, and no commented-out code.

```python
@dataclass(frozen=True, slots=True)
class InstallResult:
    path: Path
    root: Path
    written: bool
```

## Tests

- Use `tmp_path` and an injected environment. Do not read or write the real `MAYA_APP_DIR`, the home directory, or the network.
- Assert the plan (`InstallResult`, rendered `.mod` text), not only that a command exited 0.
- A new `@pytest.mark.maya` test needs a reason to touch Maya. Parser, path, and copy behavior stay unmarked.
- Do not start Maya, a GUI, or a subprocess to test a pure function.

## Releases

- `TODO.md` is the backlog. Picking a todo creates a GitHub issue before implementation.
- Each release version is a GitHub milestone. Put that issue on the milestone.

## Git and PRs

- Local identity only: `user.name=mtd3v`, `user.email=accounts@michaeltrainor.com`. Never `git config --global`.
- Remote is Cursor Origin (`origin.cursor.com`). Do not force-push `main`.
- After any session that changes code, run and fix before pushing:
  - `uv run ruff check .`
  - `uv run ruff format .`
  - `uv run pytest`
  - `uv run pre-commit run --all-files`
- Planned work: implement on a feature branch and open a PR against `main` in the same session. Do not wait to be asked.
- Small on-the-fly changes: create a branch and PR automatically. Push with `git push -u origin HEAD`.
- Keep pytest out of the git hook. Use Origin/Cursor for PRs (`gh` only if the remote is GitHub-compatible).
