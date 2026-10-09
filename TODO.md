# TODO

## Maya debug virtual environment

Add a uv virtual environment whose interpreter is Maya 2027's Python, for debugging `mtmaya`.

- Name it `.venv.maya`. Create it with `uv venv .venv.maya` after `UV_PYTHON` points at Maya's `python` next to `mayapy`. Do not use a uv-managed CPython, `python -m venv`, or pip.
- Keep `.venv.maya` separate from the project `.venv` used by pytest, ruff, and `mtm`.
- Do not put Maya's `bin/` on `PATH`. Do not install into Maya's `site-packages`. Do not add PyPI `PySide6`.
- Install `debugpy` into `.venv.maya` only. It is not a runtime dependency of the Maya module.
- On Windows, add a `scripts/windows/` helper if `scripts/macos/link-mayapy.sh` cannot create the interpreter symlink. Add `.venv.maya/` to `.gitignore`. The existing `.venv/` rule does not match it.

## Remote debug in `mtmaya.development`

Attach a debugger to a running Maya and step through `mtmaya`.

- Put the helper in `packages/mtmaya/src/mtmaya/development/` (`import mtmaya.development`). `import mtmaya` must not import it, and `userSetup.py` must not listen for a debugger.
- Start `debugpy` inside Maya from that helper (listen on a port, with an optional wait). Load `debugpy` from `.venv.maya`, not from Maya's `site-packages`.
- Document the IDE attach: host, port, and path mapping from this checkout to the installed module's `python/mtmaya`.
- Tests for the helper stay unmarked. They must not launch Maya or import `maya`.
