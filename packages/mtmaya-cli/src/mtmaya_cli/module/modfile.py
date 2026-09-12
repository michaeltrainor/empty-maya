"""Read and write Maya module description (``.mod``) specifiers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from mtmaya_cli.module import ModuleError

_TEMPLATE_NAME = "modfile.j2"
_TAG_KEYS = frozenset({"MAYAVERSION", "PLATFORM"})


@dataclass(frozen=True, slots=True)
class ModSpecifier:
    """One ``+`` specifier line from a ``.mod`` file.

    Attributes:
        name: Module name.
        version: Module version string.
        maya_version: Maya year, e.g. ``2027``.
        module_path: Fourth field; ``.``, a sibling folder name, or a path.
        platform: Maya ``PLATFORM`` tag, e.g. ``mac``.
    """

    name: str
    version: str
    maya_version: str
    module_path: str
    platform: str = "mac"


def template_environment() -> Environment:
    """Return a Jinja2 environment for packaged module templates.

    Returns:
        Environment with strict undefineds and preserved trailing newlines.
    """
    return Environment(
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def load_template(name: str) -> str:
    """Return packaged Jinja2 template text from ``templates/module``.

    Args:
        name: Template filename, e.g. ``modfile.j2``.

    Returns:
        Template source.
    """
    path = files("mtmaya_cli").joinpath("templates", "module", name)
    return path.read_text(encoding="utf-8")


def render_modfile(
    *,
    name: str,
    version: str,
    maya_version: str,
    module_path: str,
    platform: str = "mac",
    extra_lines: Sequence[str] = (),
) -> str:
    """Render a single-specifier ``.mod`` file.

    The result is the specifier line, optional path-append lines, and a
    single trailing newline. A blank line after the specifier would stop
    Maya from processing the file.

    Args:
        name: Module name.
        version: Module version string.
        maya_version: Maya year for ``MAYAVERSION``.
        module_path: ``.`` for a relocatable source tree, a sibling folder
            name after copy install, or an absolute path.
        platform: Maya ``PLATFORM`` tag.
        extra_lines: Path appends such as ``PYTHONPATH +:= python``. Empty
            lines are dropped so Maya keeps reading the definition.

    Returns:
        ``.mod`` file text.
    """
    template = template_environment().from_string(load_template(_TEMPLATE_NAME))
    rendered = template.render(
        name=name,
        version=version,
        maya_version=maya_version,
        module_path=module_path,
        platform=platform,
    )
    lines = [rendered.strip()]
    for extra in extra_lines:
        stripped = extra.strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines) + "\n"


def parse_modfile(text: str) -> ModSpecifier:
    """Parse the first ``+`` specifier line from ``.mod`` text.

    Args:
        text: Contents of a ``.mod`` file.

    Returns:
        Parsed specifier fields.

    Raises:
        ModuleError: If no specifier is present or required fields are missing.
    """
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("+"):
            return _parse_specifier(line)
    raise ModuleError("No module specifier line found.")


def _parse_specifier(line: str) -> ModSpecifier:
    tokens = line[1:].split()
    tags: dict[str, str] = {}
    positional: list[str] = []
    for token in tokens:
        key, sep, value = token.partition(":")
        if sep and not positional and key in _TAG_KEYS:
            tags[key] = value
            continue
        positional.append(token)
    if len(positional) < 3:
        raise ModuleError("Module specifier is missing name, version, or path.")
    name, version, *path_parts = positional
    return ModSpecifier(
        name=name,
        version=version,
        maya_version=tags.get("MAYAVERSION", "2027"),
        module_path=" ".join(path_parts),
        platform=tags.get("PLATFORM", "mac"),
    )


def resolve_module_path(specifier: ModSpecifier, mod_file: Path) -> Path:
    """Resolve ``ModulePath`` relative to the directory that contains the ``.mod``.

    Args:
        specifier: Parsed specifier.
        mod_file: Path to the ``.mod`` file.

    Returns:
        Absolute module root.
    """
    raw = Path(specifier.module_path)
    if raw.is_absolute():
        return raw.resolve()
    return (mod_file.parent / raw).resolve()
