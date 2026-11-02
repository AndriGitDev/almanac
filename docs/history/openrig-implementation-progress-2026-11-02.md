# OpenRig roadmap implementation checkpoints

Date: 2026-11-02. Branch: `feat/openrig-integrity`. Starting revision: `874326d`.

The [complete plan](plans/2026-11-02-openrig-inspired-memory-improvements.md)
was recovered alongside the [Almanac handoff](openrig-roadmap-handoff-2026-11-02.md) using `almanac_search` and
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

1. Review remaining work-item-1 acceptance cases and compatibility boundaries
   recorded below; the shared invalidation slice is implemented.
2. Add raw/semantic revisions, conditional writes and cache freshness.
3. Continue the plan's ordered slices: derived-source refresh; evidence schema;
   safe references; composer/preview; profiles; host epochs; adapter recovery;
   reuse policy; paired behavioral evaluation. Integration contract checks and
   deterministic tests accompany each slice. OpenRig bridge remains conditional.

No live-vault repair, broader automatic context defaults, release, push or PR
has occurred. Keep progress committed on this branch and capture a sanitized
Almanac checkpoint when handing off the session.

## Slice 2: shared eligibility at derivation and delivery boundaries

The shared policy now covers hub scans/vault maps, Inception collection (full
and incremental), Inception project-map generation and consumption, default
MCP search/query, automatic recall (including concrete queries), cached and
uncached tool context, deferred briefings, remote result envelopes, and deep
agentic suggestions. Final recall checks follow expansion/reranking. Explicit
historical search/query/read behavior is retained. Both the legacy
`hooks/memento-inception.py` and current `hooks/almanac-inception.py` are tested
as real entry points; they are separate implementations, not aliases.

Deferred records now retain source paths beside rendered lines. New records
can recheck current local validity when consumed; old records without paths
retain their existing short TTL. Agentic deep-recall records similarly retain
paths. These are additive runtime fields, not a note-schema migration.

A single invalidated-note fixture exercises the policy across consumers;
missing records retain fail-open reads, while a positively known invalidation
from the result or readable source always excludes it. No prompt-time network
lookup, LLM call or whole-vault scan was introduced. Source content freshness
and optimistic revision checks remain slice 3; unavailable remote records
cannot claim local source revalidation.

Review also found two citation-specific retry gaps: exact-text duplicate
suppression ignored new citations, and merge idempotency compared only text.
Incoming citations now bypass exact/approximate duplicate suppression when
they differ; a versioned merge marker hashes normalized incoming provenance
and text, excluding the routine date. New evidence for unchanged text survives;
identical evidence retries append once. Scoped citations remain in the body,
so the current note-level citation verifier does not claim to verify them.

A further pre-existing test isolation issue was repaired separately in
`1818579`: canonical `ALMANAC_*` credentials could override a test's legacy
`MEMENTO_*` settings, including its missing-key assertion. Test subprocesses
now exclude ambient canonical settings and per-test isolation clears both
credential namespaces. The real HTTP integration suite passes.

Validation: the focused merge/smart-store/eligibility suites pass (45 tests).
The MCP/remote gate passes (165 tests); retrieval, multi-hop, deep recall and
eval-framework suites pass (266 tests). Deterministic retrieval fixture probe,
capture/retrieve loop and release smoke pass; the loop's live extraction
case remains an intentional skip. Repository lint, formatting, compilation,
frontmatter schema and diff checks pass. The final expanded targeted/consumer
run is recorded at the final checkpoint below.

## Remaining scope

The two integrity slices start work items 1–2; they do not complete the entire
roadmap. Cue-based contradiction handling is conservative, not a semantic
proof. Review broader claim-intent compatibility and metadata-update semantics
before claiming all work-item-1 acceptance cases. Current-source invalidation
is enforced where source metadata is available; legacy opaque deferred/LLM
suggestions cannot prove source freshness. Revision-protected writes,
semantic fingerprints, remote freshness and changed-source synthesis are
next. No broader defaults or host lifecycle protocols have been enabled.

## Final checkpoint for this session

Expanded targeted and consumer suites: **504 passed**. MCP/remote: **165
passed**. Retrieval and eval-framework: **266 passed**. Combined distinct test
sets: **935 passed**. These are selected suites, not a full-suite claim. The
plan and original handoff are tracked; implementation remains on the feature
branch. Resume with the remaining acceptance audit and the revision contract.

## Extended autonomous implementation

The user authorized completing the slices locally and presenting one final PR.
All work remains on `feat/openrig-integrity`; no intermediate PR/review was opened.

The remaining implementation now includes raw/semantic revisions, thread-safe
conditional replacement and merge writes, server capability checks, revision-aware
remote sync, semantic cache invalidation and bounded timestamp-independent repair.
Inception records source fingerprints, reaches incremental refresh without new
filenames, rechecks adjudicated sources, checks source/pattern revisions before
publication, preserves refresh metadata and retains archived provenance.

Evidence capture uses the shared bounded JSON codec. Mixed/limited anchor checks
report partial/unverifiable honestly; review dates do not invalidate old knowledge.
Exact section reads share Unicode addressing, ambiguity/fence/comment handling,
contained roots and source envelopes across CLI/MCP/composition.

The opt-in composer selects indivisible source/qualification groups, validates
bounded profiles, produces pure previews and explains omissions. Generation-scoped
atomic delivery rejects stale requests/acks and supports explicit retries. CLI,
MCP and Pi expose the contract; Pi's real handlers have a local mocked-event smoke
test in addition to portable generation tests. Unsupported live-SDK/ack capabilities
are documented. Reuse/export policy inherits restrictions through derived notes,
rejects ambiguous project aliases and provides promotion drafts and export previews.

Shared contracts/examples are generated and drift-checked; project slugs and raw
paths are distinct. Wheel entry points, package inclusion, skill validation and
fresh-HOME install smoke are tested locally. The Rondo extension grades observable
actions with four matched conditions and explicit pins. Retrieval overlap alone
no longer claims measurable causal contribution. A deterministic policy fixture
is part of pytest and the eval registry; new behavior remains opt-in because no
paired stochastic live-agent experiment or live host canary has qualified defaults.

Work item 16 is intentionally conditional: no concrete OpenRig deployment was
requested, so the bridge is not implemented merely for checklist completeness.
The native versioned provider contract is ready for that future integration.

A full local run passed 2,140 tests (nine optional skips) before subsequent review
hardening. Review then added same-process thread/CAS tests, qualification retention,
incremental-source refresh and actual Pi-event smoke coverage. Final exact results
are recorded below after rerunning the complete gates.

Final pre-rebase local verification: **2,147 passed, nine optional network/model
integration tests skipped**. Static checks, schema/contract drift, deterministic
retrieval and capture/context behavior probes, fresh-HOME install smoke, wheel
entry-point smoke, native Pi handler smoke and all four edited skill validators
passed. No PR or push occurred during this implementation/testing phase.

A fetch found remote `main` at `e2cc219`, including completed rename cleanup
and removed legacy wrappers/workflow configuration. The feature delta is being
transplanted from audited base `874326d` onto that head, retaining those removals,
then local checks rerun. Earlier compatibility descriptions refer to the audited
base; final packaging follows current `main`.
