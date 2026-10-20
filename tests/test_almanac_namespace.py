"""Public Almanac entry points and naming."""

import subprocess
import sys

from almanac.mcp_inventory import registered_tool_names


def test_almanac_module_entry_point():
    result = subprocess.run([sys.executable, "-m", "almanac", "--help"], text=True, capture_output=True, check=True)
    assert "Usage: python -m almanac" in result.stdout


def test_almanac_module_dispatches_cli_tools():
    result = subprocess.run(
        [sys.executable, "-m", "almanac", "tools", "--markdown"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "<!-- almanac-mcp-tools:start -->" in result.stdout


def test_mcp_tools_use_almanac_names():
    names = registered_tool_names()
    assert len(names) == 20
    assert all(name.startswith("almanac_") for name in names)


def test_legacy_environment_variables_do_not_configure_almanac(monkeypatch):
    from almanac.env import get_env

    monkeypatch.delenv("ALMANAC_VAULT_PATH", raising=False)
    monkeypatch.setenv("MEMENTO_VAULT_PATH", "/legacy/vault")
    assert get_env("VAULT_PATH", "/default/vault") == "/default/vault"
    monkeypatch.setenv("ALMANAC_VAULT_PATH", "/almanac/vault")
    assert get_env("VAULT_PATH") == "/almanac/vault"
