# Contributing to Almanac

Almanac requires Python 3.10 or newer. Node.js 20 or newer is needed for the Pi
extension tests; Git and Bash are needed for installer and hook tests.

## Set up a checkout

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[mcp,embedded,test]' pytest ruff
```

The `test` extra in `pyproject.toml` defines the shared test dependencies. The
`embedded` extra adds the local vector-search backend. Tests that download models
or call a real LLM may require additional setup; start with the focused checks.

## Validate changes

Run these from the repository root with the virtual environment active:

```bash
python -m ruff check .
python -m ruff format --check .
python -m compileall -q almanac hooks scripts
python scripts/check_frontmatter_schema.py
python -m pytest tests/test_llm_backends.py tests/test_lifecycle.py tests/test_triage.py tests/test_store.py tests/test_frontmatter_schema.py tests/test_script_harnesses.py
python scripts/release_smoke.py
```

Run the relevant additional suites for changes to retrieval, MCP, installation,
Pi, or evaluations. `.github/workflows/ci.yml` lists the focused CI suites. The
Python script harness tests also run the Almanac Node suite.
For a full test run:

```bash
python -m pytest -q
```

CI currently treats full pytest as advisory because embedded vector-search tests
can depend on environment and model availability. Focused CI suites remain blocking.
Live-vault and LLM evaluations are opt-in; never run them as automatic gates.

For installer changes, also run the isolated install smoke:

```bash
python scripts/release_smoke.py --install-exec
```

This uses a temporary home directory. See [Releasing](docs/releasing.md) for
release checks and the interactive Pi checklist.

## Project conventions

Use `almanac/`, the `almanac` CLI, `almanac_*` MCP tools, and `ALMANAC_*`
environment variables. Memento compatibility has been retired.

The MCP tool inventory lives in `almanac/mcp_inventory.py`. After changing tool
metadata, use `python -m almanac tools --markdown` to refresh the marked tables in
`README.md` and `docs/mcp.md`, then run `python -m almanac tools --check`.

Keep changes focused, describe the resulting behavior, and include validation
results in the pull request. Standard GitHub pull requests and CI are sufficient;
no external orchestration harness or review bot is required.
