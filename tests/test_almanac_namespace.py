"""The new import path must preserve the legacy module's shared state."""

import importlib
import subprocess
import sys


def test_almanac_and_memento_import_the_same_modules():
    import almanac
    import memento

    assert almanac.__version__ == memento.__version__
    for name in ("config", "embedding", "adapters.claude", "adapters.opencode"):
        assert importlib.import_module(f"almanac.{name}") is importlib.import_module(f"memento.{name}")


def test_both_module_entry_points_remain_available():
    for module in ("almanac", "memento"):
        result = subprocess.run([sys.executable, "-m", module, "--help"], text=True, capture_output=True, check=True)
        assert f"Usage: python -m {module}" in result.stdout


def test_almanac_module_dispatches_existing_cli_tools():
    result = subprocess.run(
        [sys.executable, "-m", "almanac", "tools", "--markdown"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "<!-- memento-mcp-tools:start -->" in result.stdout
