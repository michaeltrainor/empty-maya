# TODO

Picked work becomes a GitHub issue before implementation. Each release version is a GitHub milestone. Put the issue on that milestone.

## Releases

| Version | Milestone | Scope |
| --- | --- | --- |
| 0.1.0 | [0.1.0](https://github.com/michaeltrainor/empty-maya/milestone/1) (closed) | Initial `mtmaya` runtime and `mtm` command. Recorded in `CHANGELOG.md`. Not tagged. |
| 0.2.0 | [0.2.0](https://github.com/michaeltrainor/empty-maya/milestone/2) | Windows development parity with macOS. |
| 0.3.0 | [0.3.0](https://github.com/michaeltrainor/empty-maya/milestone/3) | Debug `mtmaya` inside Maya 2027. |

## 0.3.0

### Maya debug virtual environment

[Issue #9](https://github.com/michaeltrainor/empty-maya/issues/9)

Add a uv virtual environment whose interpreter is Maya 2027's Python, for debugging `mtmaya`.

- Name it `.venv.maya`. Create it with `uv venv .venv.maya` after `UV_PYTHON` points at Maya's `python` next to `mayapy`. Do not use a uv-managed CPython, `python -m venv`, or pip.
- Keep `.venv.maya` separate from the project `.venv` used by pytest, ruff, and `mtm`.
- Do not put Maya's `bin/` on `PATH`. Do not install into Maya's `site-packages`. Do not add PyPI `PySide6`.
- Install `debugpy` into `.venv.maya` only. It is not a runtime dependency of the Maya module.
- The interpreter link is `scripts/windows/link-mayapy.ps1` on Windows and `scripts/macos/link-mayapy.sh` on macOS.
- Add `.venv.maya/` to `.gitignore`. The existing `.venv/` rule does not match it.

### Remote debug in `mtmaya.development`

[Issue #10](https://github.com/michaeltrainor/empty-maya/issues/10)

Attach a debugger to a running Maya and step through `mtmaya`.

- Put the helper in `packages/mtmaya/src/mtmaya/development/` (`import mtmaya.development`). `import mtmaya` must not import it, and `userSetup.py` must not listen for a debugger.
- Start `debugpy` inside Maya from that helper (listen on a port, with an optional wait). Load `debugpy` from `.venv.maya`, not from Maya's `site-packages`.
- Document the IDE attach: host, port, and path mapping from this checkout to the installed module's `python/mtmaya`.
- Tests for the helper stay unmarked. They must not launch Maya or import `maya`.
