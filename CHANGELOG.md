# Changelog

Notable changes to `mtmaya` and the `mtm` command. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versions match `pyproject.toml`. Nothing is tagged yet. `0.1.0` is the initial commit. Changes after that are unreleased.

## [Unreleased]

### Added

- `scripts/windows/link-mayapy.ps1` creates `python.exe` next to `mayapy.exe`, the same setup `scripts/macos/link-mayapy.sh` provides on macOS. ([#8](https://github.com/michaeltrainor/empty-maya/issues/8))
- `mtmaya.core.ui` wraps Maya UI as Qt objects and builds menus and shelves. Maya, PySide6, and shiboken6 are imported only when a helper runs. `import mtmaya` does not load this module. ([#5](https://github.com/michaeltrainor/empty-maya/pull/5))

### Changed

- `mtmaya` depends on `mtqt`. The empty `mtmaya.qt` stub is gone. `import mtmaya` does not import Qt. ([#4](https://github.com/michaeltrainor/empty-maya/pull/4))

### Fixed

- `mtm install` writes `PLATFORM` for the host (`win64`, `mac`, or `linux`) and writes module paths with forward slashes. `mtqt` is installed as a real package, because Maya does not process `.pth` files on `python/`. Modules that always said `PLATFORM:mac` were ignored on Windows. ([#2](https://github.com/michaeltrainor/empty-maya/pull/2))

## [0.1.0] - 2026-09-11

### Added

- `mtmaya`, a Maya runtime package. `import mtmaya` does not load the CLI.
- The `mtm` command: `install`, `uninstall`, `module new`, `module install`, and `version`.
- Maya module scaffold and install into `$MAYA_APP_DIR`, including `dry_run` and `force` on writes.
- `mtmaya.log` for runtime logging.

[Unreleased]: https://github.com/michaeltrainor/empty-maya/compare/2d587c14eb2581d068e3e849b5e0c6b0c1c32cb8...HEAD
[0.1.0]: https://github.com/michaeltrainor/empty-maya/commit/2d587c14eb2581d068e3e849b5e0c6b0c1c32cb8
