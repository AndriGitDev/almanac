# Almanac rename plan

Almanac is the default name for a fresh install and for every public interface. Existing Memento installations continue to work through explicit compatibility aliases and fallback paths. Historical attribution stays intact.

## Work sequence

1. Move the implementation into `almanac/`. Keep `memento/` as import and command shims. Check that old and new imports share module objects and state.
2. Publish `almanac_*` MCP tools. Keep `memento_*` aliases only in legacy mode, and migrate installed MCP clients before disabling those aliases in a running service. Update tool inventory, prompts, and tests.
3. Make fresh installs use `~/almanac`, `~/.config/almanac/almanac.yml`, Almanac hooks, skills, commands, and environment variables. Read existing Memento locations and variables as fallbacks. Do not move or overwrite an existing vault automatically.
4. Rename current docs, examples, package metadata, release artifacts, and deployment templates. Preserve upstream credit and explicitly document compatibility.
5. Run the focused and full tests, fresh-install smoke, upgrade smoke, package build, MCP protocol checks, and deployment health checks. Deploy with a reversible configuration change.

## Completion criteria

- Fresh install help, status, skills, configuration, and MCP tool list show Almanac names.
- Existing Memento imports, commands, config, and vaults still work through documented compatibility paths.
- Live service uses the new image and responds to `almanac_status`, search, and a representative write-safe read flow. Existing connected clients are migrated or legacy aliases are enabled until they are.
