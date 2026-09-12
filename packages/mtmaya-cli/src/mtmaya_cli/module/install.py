"""Install a Maya module by copying its tree and writing a sibling ``.mod``."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.modfile import parse_modfile, render_modfile, resolve_module_path
from mtmaya_cli.module.paths import user_modules_dir

_COPY_IGNORE_NAMES = frozenset(
    {".git", "__pycache__", ".venv", ".DS_Store", ".pytest_cache"}
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Outcome of a module copy install.

    Attributes:
        path: Destination sibling ``.mod`` path (Maya scans this file).
        root: Destination module tree (sibling of ``path``).
        contents: Text that was or would be written to ``path``.
        written: False when ``dry_run`` skipped the copy and write.
    """

    path: Path
    root: Path
    contents: str
    written: bool


def find_mod_file(root: Path) -> Path:
    """Locate the ``.mod`` file for a module root.

    Prefers ``{root.name}.mod``. Otherwise requires exactly one ``*.mod``.

    Args:
        root: Module source directory.

    Returns:
        Path to the ``.mod`` file.

    Raises:
        ModuleError: If no ``.mod`` is found or more than one candidate exists.
    """
    preferred = root / f"{root.name}.mod"
    if preferred.is_file():
        return preferred
    candidates = sorted(root.glob("*.mod"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ModuleError(f"No .mod file found in {root}")
    names = ", ".join(path.name for path in candidates)
    raise ModuleError(f"Multiple .mod files in {root}: {names}")


def install_module(
    source: Path,
    *,
    target: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    maya_version: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> InstallResult:
    """Copy a module tree and write a sibling ``.mod`` with a relative path.

    Copies the resolved source tree to ``{dest}/{name}/`` and writes
    ``{dest}/{name}.mod`` whose ``ModulePath`` is ``name`` (the sibling
    folder). Source ``.mod`` files are not copied into the destination tree.
    Maya scans the sibling ``.mod``, not a nested file inside ``name/``.

    Args:
        source: Module root directory (defaults to cwd at the CLI).
        target: Directory for ``{name}/`` and ``{name}.mod``. Default is
            ``$MAYA_APP_DIR/{maya_version}/modules``.
        dry_run: If true, compute the install but do not copy or write.
        force: Overwrite an existing destination tree and ``.mod``.
        maya_version: Maya year for the dest ``MAYAVERSION`` tag and, when
            ``target`` is omitted, the prefs subdirectory. Default is the
            source ``.mod`` ``MAYAVERSION``, else ``2027``.
        environ: Environment mapping for ``MAYA_APP_DIR``. ``None`` reads
            ``os.environ``.

    Returns:
        Destination ``.mod`` path, copied tree, contents, and whether a write
        occurred.

    Raises:
        ModuleError: If the source is invalid, the destination is the source
            tree, the destination exists without ``force``, or copy/write I/O
            fails.
    """
    root = source.resolve()
    if not root.is_dir():
        raise ModuleError(f"Module path is not a directory: {root}")

    mod_file = find_mod_file(root)
    try:
        specifier = parse_modfile(mod_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ModuleError(f"Cannot read {mod_file}: {exc}") from exc
    abs_root = resolve_module_path(specifier, mod_file)
    dest_maya_version = maya_version or specifier.maya_version
    contents = render_modfile(
        name=specifier.name,
        version=specifier.version,
        maya_version=dest_maya_version,
        module_path=specifier.name,
        platform=specifier.platform,
    )

    if target is not None:
        dest_dir = target
    else:
        dest_dir = user_modules_dir(maya_version=dest_maya_version, environ=environ)
    dest_mod = dest_dir / f"{specifier.name}.mod"
    dest_root = dest_dir / specifier.name
    if dest_root.resolve() == abs_root.resolve():
        raise ModuleError("Install destination is the same as the source tree.")
    if (dest_mod.exists() or dest_root.exists()) and not force:
        existing = dest_mod if dest_mod.exists() else dest_root
        raise ModuleError(f"Install already exists: {existing}")

    log.info("Installing module %s to %s", specifier.name, dest_dir)
    if dry_run:
        log.debug("Dry run; skipping copy and write")
        return InstallResult(
            path=dest_mod, root=dest_root, contents=contents, written=False
        )

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if dest_root.exists():
            shutil.rmtree(dest_root)
        shutil.copytree(abs_root, dest_root, ignore=_ignore_mod_files)
        dest_mod.write_text(contents, encoding="utf-8")
    except OSError as exc:
        raise ModuleError(
            f"Failed to install {specifier.name} to {dest_dir}: {exc}"
        ) from exc
    log.debug("Copied %s -> %s", abs_root, dest_root)
    log.debug("Wrote .mod %s", dest_mod)
    return InstallResult(path=dest_mod, root=dest_root, contents=contents, written=True)


def _ignore_mod_files(directory: str, names: list[str]) -> set[str]:
    """Exclude ``.mod`` files and junk names from a ``copytree``.

    Source ``.mod`` files stay out of the dest tree so the sibling file is
    live. VCS, caches, and OS junk are also skipped.

    Args:
        directory: Directory being copied (unused; required by ``copytree``).
        names: Entry names in ``directory``.

    Returns:
        Names that end with ``.mod`` or match ``_COPY_IGNORE_NAMES``.
    """
    _ = directory
    return {
        name for name in names if name.endswith(".mod") or name in _COPY_IGNORE_NAMES
    }
