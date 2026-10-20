# Working on Almanac

Almanac is a Python knowledge vault with shell installers and a TypeScript Pi extension.
See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and validation commands.

- `almanac/` is the Python package. Use Almanac names for code, commands,
  environment variables, and documentation; Memento compatibility is retired.
- Keep the vault focused on curated knowledge; run logs and evidence belong to the runner.
- Update `almanac/mcp_inventory.py` when changing MCP tools, then use
  `python -m almanac tools --markdown` to refresh the marked tables in `README.md`
  and `docs/mcp.md`.
- Run the checks relevant to your changes before handing them off. CI is defined in
  `.github/workflows/ci.yml`; no external harness or review bot is required.
