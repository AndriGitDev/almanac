# Releasing Almanac

## Release checks

Set up the contributor environment and run the checks in
[CONTRIBUTING.md](../CONTRIBUTING.md), then run:

```bash
python scripts/release_smoke.py
python scripts/release_smoke.py --install-exec
```

The default smoke checks CLI and module help/version paths, package metadata,
Homebrew formula metadata, version consistency, and shell syntax. The install
execution smoke exercises a non-interactive install in a temporary home directory.

Optional checks validate Docker Compose configuration and an npm package dry-run
when the tools are available:

```bash
python scripts/release_smoke.py --heavy
```

CI runs lint, format, compile checks, focused test suites, hermetic evaluations,
release and install smoke checks, and shell syntax on macOS Bash 3.2. Full pytest
is currently advisory because of embedded vector-search environment dependencies.
Live-vault, LLM, and authenticated Claude smoke checks remain opt-in locally.

## Version and release

1. Update `VERSION`, `package.json`, `almanac/__init__.py`, and
   `Formula/almanac.rb` to the release version. The formula URL must use that tag.
2. Run the release checks and merge the release PR to `main`.
3. Tag the release from the updated `main` branch:

```bash
git checkout main
git pull --ff-only origin main
git tag vX.Y.Z
git push origin vX.Y.Z
```

Draft release notes from `git log --oneline vPREVIOUS..vX.Y.Z` and create the GitHub
release. Compute the source archive checksum and update `Formula/almanac.rb`:

```bash
curl -fL -o almanac-vX.Y.Z.tar.gz \
  https://github.com/AndriGitDev/almanac/archive/refs/tags/vX.Y.Z.tar.gz
shasum -a 256 almanac-vX.Y.Z.tar.gz
```

Where Homebrew is available, validate the updated formula:

```bash
brew install --build-from-source ./Formula/almanac.rb
brew test almanac
almanac version
```

## Pi bridge release smoke checklist

From a checkout, start the extension:

```bash
pi -e ./extensions/almanac.ts
```

Verify `/almanac-status`, `/almanac-queue`, `/reload`, `/new`, `/resume`, `/fork`,
`/compact`, and quit. The bridge uses short-lived `python3 -m almanac.pi_bridge`
calls; shutdown should leave no Almanac-owned child processes behind.
