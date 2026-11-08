"""The CLI imports only names in gift_genius.__all__, never back end submodules."""

import ast
from pathlib import Path

import gift_genius
import gift_genius_cli

SOURCE = Path(gift_genius_cli.__file__).parent


def test_cli_uses_only_the_public_api():
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("gift_genius."), f"{path}: import {alias.name}"
                    assert alias.name != "anthropic", f"{path} talks to Claude directly"
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                assert not node.module.startswith("gift_genius."), f"{path}: from {node.module}"
                if node.module == "gift_genius":
                    for alias in node.names:
                        assert alias.name in gift_genius.__all__, f"{path}: {alias.name} is not public"


def test_cli_install_does_not_need_the_api_extra():
    text = (SOURCE.parents[1] / "pyproject.toml").read_text()
    assert '"gift-genius-backend",' in text and "[api]" not in text.split("dependencies")[1].split("]")[0]
