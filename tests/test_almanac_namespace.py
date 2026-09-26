"""The new import path must preserve the legacy module's shared state."""

import importlib
import os
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
    assert "<!-- almanac-mcp-tools:start -->" in result.stdout


def test_mcp_tool_names_default_to_almanac_and_legacy_mode_adds_aliases():
    script = "from almanac.mcp_server import mcp; print(' '.join(sorted(mcp._tool_manager._tools)))"
    clean_env = {**os.environ, "ALMANAC_LEGACY_MCP_TOOLS": "0"}
    default = subprocess.run([sys.executable, "-c", script], env=clean_env, text=True, capture_output=True, check=True)
    names = set(default.stdout.split())
    assert len(names) == 20
    assert all(name.startswith("almanac_") for name in names)

    clean_env["ALMANAC_LEGACY_MCP_TOOLS"] = "1"
    legacy = subprocess.run([sys.executable, "-c", script], env=clean_env, text=True, capture_output=True, check=True)
    legacy_names = set(legacy.stdout.split())
    assert len(legacy_names) == 40
    assert names <= legacy_names
    assert {name.replace("almanac_", "memento_", 1) for name in names} <= legacy_names
