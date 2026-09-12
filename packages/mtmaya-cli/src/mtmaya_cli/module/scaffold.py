"""Scaffold a relocatable Maya module source tree."""

from __future__ import annotations

import logging
from pathlib import Path

from mtmaya_cli.module import ModuleError
from mtmaya_cli.module.modfile import (
    load_template,
    render_modfile,
    template_environment,
)
from mtmaya_cli.module.paths import DEFAULT_MAYA_VERSION

log = logging.getLogger(__name__)
MODULE_SUBDIRS = ("scripts", "plug-ins", "icons", "presets")
"""Maya module folders created by ``mtm module new``."""

_PLUGIN_TEMPLATE = "plugin.py.j2"
_USER_SETUP_TEMPLATE = "userSetup.py.j2"


def validate_name(name: str) -> str:
    """Return ``name`` if it is a valid Maya module directory name.

    Args:
        name: Candidate module name.

    Returns:
        The same name.

    Raises:
        ModuleError: If the name is empty, has whitespace, or path separators.
    """
    if not name:
        raise ModuleError("Module name must not be empty.")
    if any(ch.isspace() for ch in name):
        raise ModuleError("Module names cannot contain spaces.")
    if "/" in name or "\\" in name:
        raise ModuleError("Module names cannot contain path separators.")
    if name in {".", ".."}:
        raise ModuleError("Module name is invalid.")
    return name


def render_user_setup(name: str, *, startup_import: str | None = None) -> str:
    """Render ``scripts/userSetup.py`` from the packaged template.

    Args:
        name: Module name shown in the stub docstring.
        startup_import: Optional package to import at Maya init (no Maya
            APIs). ``None`` writes the comment-only stub.

    Returns:
        File text with a trailing newline.
    """
    template = template_environment().from_string(load_template(_USER_SETUP_TEMPLATE))
    text = template.render(name=name, startup_import=startup_import or "")
    if not text.endswith("\n"):
        text += "\n"
    return text


def write_user_setup(
    root: Path, name: str, *, startup_import: str | None = None
) -> Path:
    """Write ``scripts/userSetup.py`` under a module root.

    Args:
        root: Module root directory.
        name: Module name shown in the stub docstring.
        startup_import: Optional package to import at Maya init.

    Returns:
        Path to the written file.
    """
    path = root / "scripts" / "userSetup.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_user_setup(name, startup_import=startup_import), encoding="utf-8"
    )
    return path


def create_module(
    name: str,
    *,
    directory: Path,
    version: str = "0.1.0",
    maya_version: str = DEFAULT_MAYA_VERSION,
    with_plugin: bool = False,
    with_user_setup: bool = False,
    startup_import: str | None = None,
    force: bool = False,
) -> Path:
    """Write a relocatable module tree under ``directory / name``.

    Does not touch Maya preferences. The source ``.mod`` uses ``.`` as
    ``ModulePath`` so the tree can be moved before a copy install.

    Args:
        name: Module name (directory and ``.mod`` stem).
        directory: Parent directory for the new module tree.
        version: Module version written into the ``.mod`` file.
        maya_version: Maya year for ``MAYAVERSION``.
        with_plugin: If true, write a Python plug-in stub.
        with_user_setup: If true, write ``scripts/userSetup.py``.
        startup_import: Package imported from ``userSetup.py`` when
            ``with_user_setup`` is true. ``None`` writes the comment-only stub.
        force: Overwrite generated files if the destination already exists.
            Rewrites the ``.mod`` and optional stubs this call generates, and
            deletes leftover plugin / ``userSetup.py`` stubs it is not writing.

    Returns:
        Absolute path to the created module root.

    Raises:
        ModuleError: If the name is invalid, the destination exists without
            ``force``, or mkdir/write I/O fails.
    """
    validate_name(name)
    root = (directory / name).resolve()
    if root.exists() and not force:
        raise ModuleError(f"Destination already exists: {root}")
    if root.exists() and root.is_file():
        raise ModuleError(f"Destination is a file, not a directory: {root}")

    log.info("Creating module %s at %s", name, root)
    plugin_path = root / "plug-ins" / f"{name}.py"
    setup_path = root / "scripts" / "userSetup.py"
    try:
        for subdir in MODULE_SUBDIRS:
            (root / subdir).mkdir(parents=True, exist_ok=True)

        mod_text = render_modfile(
            name=name,
            version=version,
            maya_version=maya_version,
            module_path=".",
        )
        mod_path = root / f"{name}.mod"
        mod_path.write_text(mod_text, encoding="utf-8")
        log.debug("Wrote .mod %s", mod_path)

        if with_plugin:
            template = template_environment().from_string(
                load_template(_PLUGIN_TEMPLATE)
            )
            plugin_text = template.render(name=name)
            if not plugin_text.endswith("\n"):
                plugin_text += "\n"
            plugin_path.write_text(plugin_text, encoding="utf-8")
            log.debug("Wrote plugin stub %s", plugin_path)
        elif force:
            plugin_path.unlink(missing_ok=True)
            log.debug("Removed leftover plugin stub %s", plugin_path)

        if with_user_setup:
            write_user_setup(root, name, startup_import=startup_import)
            log.debug("Wrote userSetup stub %s", setup_path)
        elif force:
            setup_path.unlink(missing_ok=True)
            log.debug("Removed leftover userSetup stub %s", setup_path)
    except OSError as exc:
        raise ModuleError(f"Failed to create module {name}: {exc}") from exc

    return root
