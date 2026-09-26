"""Compatibility entry point for ``python -m memento``."""

from almanac.__main__ import main
import os

if __name__ == "__main__":
    os.environ.setdefault("ALMANAC_LEGACY_MCP_TOOLS", "1")
    raise SystemExit(main(prog="python -m memento"))
