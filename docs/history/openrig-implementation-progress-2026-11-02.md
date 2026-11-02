# OpenRig roadmap implementation checkpoints

Date: 2026-11-02. Branch: `feat/openrig-integrity`. Starting revision: `874326d`.

The [complete plan](plans/2026-11-02-openrig-inspired-memory-improvements.md)
was recovered alongside the Almanac handoff using `almanac_search` and
`almanac_get` (embedded search). Its previously ignored local file is now
tracked in commit `9d673e3`. This log records implementation checkpoints;
it does not mark the complete roadmap implemented.

## Slice 0: establish verification

Installed missing pytest and ruff in the existing virtual environment with
`uv pip install --python .venv/bin/python pytest ruff` (pip was absent too).
The original merge/smart-store baseline passed: 24 tests. New regressions
then failed in six places before the repair.

A broader run exposed two existing test problems: the renamed collection
assertion still expected `memento`, and a threshold-miss fixture allowed PRF
queries beyond its two mocked responses. Commit `173b962` corrects the
assertion to `almanac` and disables PRF in that fixture. Both focused tests pass.

## Slice 1: metadata-preserving merge and candidate boundaries

- Preserve canonical frontmatter, including unknown multiline values,
  citations, origin, date, project identity, lineage and validity conditions.
  Only union tags. Established certainty is not increased automatically.
- Append incoming provenance and citations under the corresponding merge
  section, without asserting that evidence for the original claim.
- Inspect up to five embedding candidates. Require an existing, contained,
  parseable note with active validity and matching normalized project identity.
  Unscoped notes only merge with unscoped incoming notes.
- Repeat eligibility under the existing reentrant vault write lock. Use the
  shared atomic writer so a failed rename preserves the original and cleans
  temporary files.
- Honor replacement cues before embedding merge and approximate duplicate
  suppression. Explicit supersession takes the review path. This is a
  conservative cue-based guard, not a semantic contradiction proof.
- Preserve incoming citations through smart-store and expose merge rejection
  reasons. Filter invalidated/cross-project exact-match candidates too.
- Add merge/smart-store tests to CI and Beislið/Rondo gate commands, including
  the process artifact and gate contract tests.

Validation: 34 focused merge/smart-store tests pass. Repository-wide ruff,
format check, compileall and frontmatter schema checks pass. The hermetic
capture/retrieve loop passes (one live extraction case is intentionally skipped).
Release smoke passes. The expanded targeted gate passes: 428 tests.

## Next slices and resume point

1. Finish shared eligibility across hubs, Inception, graph expansion, cached
   tool context and deferred/agentic automatic retrieval. Keep explicit history.
2. Add raw/semantic revisions, conditional writes and cache freshness.
3. Continue the plan's ordered slices: derived-source refresh; evidence schema;
   safe references; composer/preview; profiles; host epochs; adapter recovery;
   reuse policy; paired behavioral evaluation. Integration contract checks and
   deterministic tests accompany each slice. OpenRig bridge remains conditional.

No live-vault repair, broader automatic context defaults, release, push or PR
has occurred. Keep progress committed on this branch and capture a sanitized
Almanac checkpoint when handing off the session.
