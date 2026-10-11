# TODO

Picked work becomes a GitHub issue before implementation. Each release version is a GitHub milestone. Put the issue on that milestone.

## Releases

| Version | Milestone | Scope |
| --- | --- | --- |
| 0.1.0 | [0.1.0](https://github.com/michaeltrainor/empty-maya/milestone/1) (closed) | Initial `mtmaya` runtime and `mtm` command. Recorded in `CHANGELOG.md`. Not tagged. |
| 0.2.0 | [0.2.0](https://github.com/michaeltrainor/empty-maya/milestone/2) | Windows development parity with macOS. |
| 0.3.0 | [0.3.0](https://github.com/michaeltrainor/empty-maya/milestone/3) | Debug `mtmaya` inside Maya 2027. |

## 0.3.0

### Remote debug in `mtmaya.development`

[Issue #10](https://github.com/michaeltrainor/empty-maya/issues/10)

Attach a debugger to a running Maya and step through `mtmaya`.

- Put the helper in `packages/mtmaya/src/mtmaya/development/` (`import mtmaya.development`). `import mtmaya` must not import it, and `userSetup.py` must not listen for a debugger.
- Start `debugpy` inside Maya from that helper (listen on a port, with an optional wait). Load `debugpy` from `.venv.maya`, not from Maya's `site-packages`.
- Document the IDE attach: host, port, and path mapping from this checkout to the installed module's `python/mtmaya`.
- Tests for the helper stay unmarked. They must not launch Maya or import `maya`.
