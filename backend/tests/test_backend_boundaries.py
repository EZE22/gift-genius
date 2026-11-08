"""The back end never imports a front end, and the CLI-only install has no API dependencies."""

import ast
import tomllib
from pathlib import Path

import gift_genius

SOURCE = Path(gift_genius.__file__).parent


def test_back_end_never_imports_a_front_end():
    """No backend source file imports gift_genius_cli. The dependency points the other way."""
    files = sorted(SOURCE.rglob("*.py"))
    assert len(files) > 10
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert not module.startswith("gift_genius_cli"), f"{path} imports {module}"


def test_api_dependencies_are_an_optional_extra():
    """FastAPI and uvicorn are in the api extra, so a CLI install does not pull them in."""
    project = tomllib.loads((SOURCE.parents[1] / "pyproject.toml").read_text())["project"]
    assert not any(d.startswith(("fastapi", "uvicorn")) for d in project["dependencies"])
    assert any(d.startswith("fastapi") for d in project["optional-dependencies"]["api"])


def test_public_api_does_not_import_fastapi():
    """Importing gift_genius (the public API) must not require FastAPI. Only api/ may mention it."""
    for path in SOURCE.rglob("*.py"):
        if "api" in path.relative_to(SOURCE).parts[:1]:
            continue
        assert "fastapi" not in path.read_text(), path
