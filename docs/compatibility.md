# Memento compatibility

Fresh installs use the `almanac` CLI, `almanac_*` MCP tools, `/almanac` skills, `~/almanac` vault, and `~/.config/almanac/almanac.yml`. Existing vaults stay in place; the installer never copies a backup mirror over a vault or moves notes automatically.

Existing Python imports under `memento` resolve to the same modules as `almanac`. `python -m memento` and the existing `memento-vault` wrapper still run. The legacy Python command also registers `memento_*` MCP aliases so old stdio clients keep working. A server started with `python -m almanac` exposes only Almanac tools by default; set `ALMANAC_LEGACY_MCP_TOOLS=1` during an HTTP client transition.

Almanac environment variables take precedence over the matching `MEMENTO_*` variables. The config loader reads Almanac locations first and then legacy Memento locations. Existing `~/memento` vaults are reused when no Almanac vault or explicit path is present. The old vault file format remains readable, and archive import/export retains its state files.

To update an old install, run `./install.sh`. It adds the Almanac CLI, hooks, skills, and MCP registration while preserving the existing vault path from the install manifest. Once your clients use `almanac_*` tools, you can remove their old `memento-vault` MCP registration. Keep legacy tool aliases enabled on a remote server until all connected clients have migrated.
