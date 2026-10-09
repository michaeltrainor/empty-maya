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
        deferred = _module_level_roots(tree)
        assert "maya" not in deferred, path
        assert "PySide6" not in deferred, path
        assert "shiboken6" not in deferred, path


def _module_level_roots(tree: ast.AST) -> list[str]:
    """Return imports executed when the module is imported."""
    names: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            _ = node

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            _ = node

        def visit_Lambda(self, node: ast.Lambda) -> None:
            _ = node

        def visit_If(self, node: ast.If) -> None:
            if _is_type_checking(node.test):
                return
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            names.extend(alias.name.split(".")[0] for alias in node.names)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module:
                names.append(node.module.split(".")[0])

    Visitor().visit(tree)
    return names


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False
