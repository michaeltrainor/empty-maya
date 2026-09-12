import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "packages" / "mtmaya" / "src" / "mtmaya"
CLI = ROOT / "packages" / "mtmaya-cli" / "src" / "mtmaya_cli"


def _imported_roots(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
    return names


def test_cli_does_not_import_maya() -> None:
    for path in CLI.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert "maya" not in _imported_roots(tree), path


def test_runtime_does_not_import_cli() -> None:
    for path in RUNTIME.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        roots = _imported_roots(tree)
        assert "mtmaya_cli" not in roots, path
        assert "typer" not in roots, path
        assert "jinja2" not in roots, path
        assert "maya" not in roots, path
