# Almanac memory integrity and context delivery plan

Status: proposed implementation roadmap. Date: 2026-11-02.

Almanac should preserve trustworthy knowledge through edits and synthesis, deliver the right complete context at each session boundary, and measure whether that context improves agent behavior. Implement the correctness foundations before expanding automatic delivery. Keep Markdown as the durable source and reuse the existing retrieval, capture, health, and automation contracts.

This plan compares Almanac commit `874326d47a50ac59496c38c109deb196cbc46a02` with OpenRig commit `bf350515376767ffb1bb1edea429e7bdf1a17c6a`. References to OpenRig below are pinned to that revision. Implementation names and new API fields are proposed; none of the new features are enabled by this document.

## Findings that change the priorities

### Confirmed with isolated temporary vaults

1. `merge_into_canonical` drops existing `citations`, `invalidated_by`, `pinned`, `synthesized_from`, `last_resurfaced`, and `validity-context` when the incoming merge does not supply replacements. The probe created a note with those fields and inspected the rewritten file. This can erase both the evidence and the fact that a claim was invalidated. See [merge implementation](../../../almanac/dedup_merge.py).
2. `find_merge_target` accepts an invalidated note when an embedding backend returns it as the best match. It has no incoming project parameter. The probe used a fake backend returning a note from another project; the function accepted that candidate. This proves missing eligibility checks at that boundary, not how often production embeddings select such a note.
3. `collect_eligible_notes(..., full=True)` includes a note carrying `invalidated_by`. Inception uses that collection for clustering. The probe exercised the real collector without running an LLM. See [Inception](../../../hooks/almanac-inception.py).
4. The hub scanner retains an invalidated note and does not carry its invalidation metadata into the hub metadata object. The downstream project selection does not filter invalidation. See [hub generation](../../../almanac/hub.py).

### Source findings

- Inception's synthesis ledger compares source-name sets. An unchanged set is skipped even though the source contents could have changed. Source fingerprints are needed to distinguish repeated work from changed evidence.
- Session packets slice assembled strings to fit a character budget. Recall and tool-context formatters also shorten snippets. A packet can lose a condition or rationale even when truncation is reported. See [lifecycle](../../../almanac/lifecycle.py) and [retrieval policy](../../../almanac/retrieval_policy.py).
- Pi already captures around compaction, but its compaction handler does not request a dedicated recovery packet. This is a delivery extension, not a missing capture integration. See [Pi extension](../../../extensions/almanac.ts).
- Runtime state already uses host/project/session/cwd scoping and locks. It does not model a separate context generation after compaction; MCP wrappers identify their host as the shared string `mcp`.
- Tool-context caches use TTL freshness. Note content and validity changes need explicit freshness checks before cached material is injected.
- The Rondo outcome classifier can label memory relevant based on note references or query-intent overlap. That does not prove the agent applied the lesson or that it improved the outcome. Extend [the existing benchmark](../../../benchmark/rondo/evaluation.py).
- Skills still contain examples assigning a filesystem path to `project`, although the current schema specifies a stable slug and separate `project_path`. Shared examples need parity checks against the schema.

The attempted selected pytest run could not start because `.venv/bin/python` has no `pytest` module. The isolated probes above used Python and temporary files with indexing and other persistent side effects mocked where needed. They did not edit the real vault. A full correctness audit remains an implementation prerequisite, not a claimed result of this review.

## Existing capabilities to retain

Almanac already has hybrid retrieval, graph expansion, agentic retrieval, explicit search/get, metadata queries, citation checks, supersession chains, atomic writes, write locks, capture idempotency, remote retry state, archive manifests, reversible archival, bounded hubs, diagnostics, and deterministic evaluation suites. Several advanced features are opt-in. Their presence does not mean they are enabled in a particular installation.

The installer already protects local edits with recorded hashes, three-way merge, and side files. Extend its coverage rather than importing OpenRig's projection database. Likewise, extend the existing archive, benchmark, and health surfaces rather than creating parallel systems.

## Ownership and compatibility rules

- Almanac owns curated knowledge, retrieval policy, memory packet composition, and bounded memory-delivery bookkeeping.
- Hosts own live conversations, compaction events, active task state, and whether context was attached to a turn.
- Rondo or another runner owns task execution, transcripts, run evidence, and outcome records. Beislið owns work and verification contracts.
- Runtime delivery state, pending review candidates, and caches remain outside the searchable vault. Reuse existing runtime directories and locking conventions.
- Preserve existing tools, response fields, legacy imports, and `memento_*` compatibility where currently supported. Introduce fields additively and version new contracts.
- Memory remains optional by default. A missing source is reported precisely; it does not silently turn into an empty success. Explicit required-context requests may return an incomplete result for the caller to act on.
- Note content remains evidence, not executable configuration or higher-priority instructions. A remembered shell command is never automatically run by verification machinery.

## Target architecture

Use one shared path for source resolution, eligibility checks, composition, and rendering:

`request -> resolve scope -> gather candidates -> check eligibility -> resolve complete pieces -> select within budget -> render -> adapter delivery`

Candidate gathering continues using Almanac's existing search and graph implementations. A small composition layer owns the remaining selection and rendering behavior. Background maintenance handles source-change propagation, evidence review, and synthesis refresh. This keeps LLM work and whole-vault scans off prompt-time paths.

A proposed packet request adds optional `situation`, `context_epoch`, `host_instance_id`, and `profile` fields to the existing session-context request. Situations are `fresh`, `resume`, and `post_compaction`; omission preserves the legacy path during rollout. Host capabilities describe observable behavior, such as whether a compaction event or delivery acknowledgment exists. The server must not infer those capabilities from a provider name alone.

A proposed `ContextPiece` contains a vault-relative reference, optional section address, source revision, rendered-content hash, purpose, priority, estimated tokens, validity/evidence status, and text. An optional dependency list refers only to explicit composition prerequisites. Wikilinks continue to mean related knowledge; they are not automatically prerequisites.

A versioned packet returns selected pieces, bounded omission summaries, expandable references, budget accounting, completeness, and a packet identifier. Preserve `content`, `results`, and `metadata` for existing clients. The actual response should avoid serializing the same large text twice: structured pieces can contain offsets or be requested as a separate detailed representation.

## Phase 1 Preserve knowledge integrity

### Work item 1 Preserve metadata and constrain merges

**Change.** Route merge rewrites through the shared frontmatter parser and metadata-preserving write machinery. Preserve unknown fields as well as citations, source lineage, invalidation, pinning, resurfacing, project identity, and validity conditions. Distinguish an omitted field from an explicit request to change it. Retain incoming citation and evidence provenance without replacing the origin of the original claim.

Embedding similarity should propose a candidate. Before accepting it, verify current existence, active validity, compatible project/reuse scope, and compatible claim intent. A superseding or contradictory claim must follow the supersession/review path rather than append to the obsolete claim. Search several bounded candidates and choose an eligible one instead of accepting the first result regardless of scope.

Do not automatically raise certainty just because merged input claims higher certainty. Preserve the established claim's confidence unless a deliberate evidence-based update justifies a change.

**Touchpoints.** `almanac/dedup_merge.py`, `smart_store.py`, `frontmatter.py`, `store.py`, and capture callers.

**Acceptance.** Regression fixtures retain all existing fields and unknown multiline metadata; incoming citations survive; invalidated and incompatible-project candidates cannot be automatic merge targets; contradictory updates remain distinct; idempotent retries produce one merge; failures leave the original file readable. Tests cover every public path that reaches the merge helper.

### Work item 2 Apply one eligibility policy everywhere

**Change.** Introduce a shared note-eligibility function with explicit purposes: current-context retrieval, synthesis input, merge target, and historical inspection. Reuse existing validity parsing and project filters. Apply it to cached and uncached tool context, hubs, vault maps, deferred/agentic retrieval results, graph expansion outputs, merge selection, and Inception inputs.

Explicit historical reads may still retrieve invalidated material, but must return its status. Active hubs and synthesis must not present it as current guidance. Apply final checks after candidate expansion and again when material is read from caches.

**Acceptance.** One invalidated-note fixture is exercised across all these surfaces. Default current-context paths exclude it; explicit history includes and labels it. Missing metadata, unavailable remote records, and malformed notes have documented outcomes. Optional memory failure remains fail-open while a positively known invalidation is always respected.

### Work item 3 Track source revisions and prevent stale overwrites

**Change.** Define two hashes with distinct meanings: a raw-file revision for optimistic concurrency, and a semantic revision for freshness. The semantic revision includes claim text, validity, citations, evidence, and reuse policy, but excludes access counters and routine resurfacing timestamps.

Return revisions from known-note reads. Add optional `expected_revision` to replace/merge operations and compare it under the existing write lock. Upgrade remote sync to use this condition after reading a conflict candidate. Return a structured conflict without overwriting intervening edits. Older servers must report unsupported conditional writes; a client requiring the guarantee must not silently retry unconditionally.

Use revisions to invalidate or revalidate derived caches. Add a bounded repair scan for out-of-band edits, including preserved-mtime cases. Reuse the embedded index and current indexer rather than making a new database service.

**Acceptance.** Concurrent writers cannot silently overwrite each other when using the precondition; unchanged retries are idempotent; an access-count update does not invalidate synthesis; a changed claim or invalidation does invalidate cached use; changes with preserved timestamps are eventually detected by repair.

**Dependencies.** Work items 1 and 2 establish write and eligibility semantics before freshness caching is expanded.

## Phase 2 Make learning evidence aware

### Work item 4 Retain situation and rationale during capture

**Change.** Extend existing capture contracts and prompts with optional evidence method, compact evidence summary, applicability, recommended action, and invalidating conditions. Reuse `validity-context`, citations, automated-run evidence summaries, and artifact references wherever their semantics already fit. Add fields only when a consumer needs them.

Use a situation/action/because structure for procedural advice. Keep facts and decisions free to use a simpler form. Record whether support comes from an observation, code check, human decision, or synthesis. Repeated retrieval is usage evidence, not independent confirmation.

Retain the current certainty scale and separate it from recency, durability, audience, and verification status. New nested metadata must have a shared supported encoding and decoder; do not quietly introduce YAML shapes the dependency-free frontmatter parser cannot read.

**Acceptance.** A caveat survives capture and subsequent merging. Unsupported evidence is not fabricated. Historical notes remain readable without backfilling guessed provenance. Capture evaluations distinguish useful durable lessons from status reports and unjustified generalizations.

### Work item 5 Refresh synthesis when its evidence changes

**Change.** Extend `synthesized_from` with semantic revisions of the source notes and maintain a derived reverse-dependency index. Refresh candidates include source edits and invalidations, not only newly added source names. Re-read eligibility after contradiction adjudication before using the same in-memory source collection for synthesis.

When a supporting claim changes or becomes invalid, mark the pattern as needing review and schedule bounded re-evaluation. A changed source does not automatically prove the conclusion false. Preserve the old pattern until an explicit replacement or reviewed update is ready. Archiving a source also does not prove it false: resolve archived provenance where available and distinguish moved, unavailable, changed, and invalidated sources.

Protect active provenance references during archival, or retain resolvable archival references. Use the existing sweeper, reversible archive, synthesis budgets, and runtime review queues. Avoid recursive synthesis of generated patterns into progressively unsupported claims.

**Acceptance.** A source edited under the same filename causes refresh; source invalidation flags dependents; telemetry-only changes do not trigger synthesis; deleted sources produce a visible provenance gap; failed synthesis preserves the prior readable note; a refresh cannot publish against source revisions that changed during generation.

### Work item 6 Extend verification at use

**Change.** Expose structured citation/evidence status consistently in search, get, context pieces, and explain output. Distinguish verified anchors, partial checks, stale anchors, unavailable repository context, and absent evidence. A matching code substring verifies the anchor, not the semantic truth of an entire note.

Add optional review dates and safe built-in checks for volatile facts where useful. Prefer references to live authoritative sources over copying transient counts, branch state, or deployment status into durable guidance. Any command-based verification remains an explicit host action; no arbitrary note-authored code execution.

**Acceptance.** Missing files and inaccessible repositories are not automatically declared contradictions. A mixed set of verifiable/unverifiable citations is represented accurately. Verification remains bounded to selected notes; review work is deferred; useful old notes are not invalidated by age alone.

**Dependencies.** Work items 3 and 4 supply revision and evidence semantics; work item 5 consumes them for maintenance.

## Phase 3 Compose complete and inspectable context

### Work item 7 Add section-level references

**Change.** Extend known-note reads to resolve a whole note or an exact section such as `notes/cache-policy.md#applicability`. Use one shared Markdown section resolver across CLI, MCP, and packet composition. Whole-note calls retain their existing behavior.

Retain source and validity metadata in an envelope even when returning only one section. Detect duplicate/ambiguous headings, missing sections, fenced-code headings, comments, malformed fences, and Unicode slug collisions. Define a stable slug grammar rather than copying OpenRig's ASCII-only assumptions without review.

Restrict references to configured roots and reject traversal and symlink escapes before reading bytes. Never fall back from a missing section to an unrelated fuzzy match. Keep external handoff files host-owned: hosts may compose their own state alongside Almanac packets without copying that state into notes.

**Acceptance.** Exact section spans preserve conditions and child sections according to the documented grammar; errors distinguish missing file, missing section, ambiguity, and denied source; metadata cannot disappear through section extraction; local and remote representations agree.

### Work item 8 Select whole pieces within the budget

**Change.** Build a pure composition module that selects complete pieces or pre-authored bounded summaries. Replace arbitrary slicing at packet, recall, tool-context, and host-adapter boundaries. Preserve caveats, stale markers, source labels, and expansion references as part of the selected unit.

Resolve explicit prerequisites before budgeting. Reject cycles in authored profiles. When a dependency group cannot fit, omit the group and explain why; do not inject advice without its required qualification. Keep dependency expansion bounded by count and depth.

Separate content budget from response-envelope overhead. Label character/byte-based token counts as estimates; support exact tokenizer accounting only where available. Handle budgets too small even for one useful piece with a compact incomplete result. Bound the omission report itself.

**Acceptance.** Tiny budgets do not cut a condition in half or produce malformed output. Unicode and escaping are covered. Rendered output matches selected-piece metadata. Prerequisites cannot be dropped independently. Legacy callers retain compatible fields. No new LLM call is introduced on the normal composition path.

### Work item 9 Add named context views and progressive disclosure

**Change.** Offer a small set of explicit views such as project orientation, debugging, design review, and recovery. Start with built-in selectors over existing note types, evidence, project hubs, and query relevance. Then allow versioned repository/user profiles referencing canonical notes and sections, with priorities and optional prerequisites.

Use the existing bounded hubs as the orientation layer and section/get reads as the depth layer. A compact index can say which note is relevant at which task moment; it should not preload the entire knowledge graph. Profiles are configuration, not new copies of note content or a general workflow language.

**Acceptance.** Profile inspection explains selection and order before delivery. Missing required references are visible. Optional sources degrade independently. Broad orientation stays within budget. Existing no-profile retrieval remains the default until measured improvements justify a change.

**Dependencies.** Work items 2, 3, 6, and 7 supply eligibility, revision, evidence, and addressing before work items 8 and 9 expand composition.

## Phase 4 Make delivery aware of session boundaries

### Work item 10 Add fresh, resume, and post-compaction context

**Change.** Extend the shared lifecycle request and adapters with the optional situation, host instance, and context epoch fields described above. Fresh context emphasizes project orientation and applicable constraints. Resume context emphasizes relevant durable decisions and changed evidence. Post-compaction context restores critical applicable lessons and pointers to host-owned handoff state. The host supplies current intent when available; Almanac must not reconstruct active tasks from old notes.

Increment or replace the context epoch when the host reports a new context generation. Reset delivery deduplication for that generation without erasing the session's durable capture history. Pi can explicitly request recovery after its compaction event. MCP and CLI callers can pass the same fields; adapters without that event keep their existing behavior. Maintain a capability matrix showing what each adapter can actually observe.

**Touchpoints.** `almanac/lifecycle.py`, MCP tool schemas and wrappers, CLI session-context commands, `extensions/almanac.ts`, and the existing host hooks. Confirm actual entry points when implementing rather than adding a second lifecycle service.

**Acceptance.** A note delivered before compaction can be restored afterward without being repeatedly injected on ordinary prompts. Two clients sharing a server do not share delivery state accidentally. Resume does not present an old task as current. Legacy callers continue to work. Each supported adapter has a native smoke test; unsupported event capabilities are reported honestly.

### Work item 11 Make delivery bookkeeping observable and race-safe

**Change.** Give composed packets stable identifiers and scope bookkeeping by vault, host instance, project/checkout, session, and context epoch. Distinguish packet preparation, return to a caller, and host acknowledgment where supported. None proves the model used the content. Use existing locks and generation checks to prevent an older in-flight request from overwriting newer recovery state.

Define bounded retry and deduplication behavior for interrupted requests. Retain retryable work after a delivery failure. Do not promise exactly-once delivery where a host cannot acknowledge attachment. Optional memory failure should leave the user's turn usable while returning a diagnostic. Avoid new network calls, LLM calls, or whole-vault scans in a prompt hook.

**Acceptance.** Deterministic interleaving tests cover simultaneous prompt and compaction events, two clients, retry after timeout, stale acknowledgments, and restart during state publication. An old epoch cannot mark a new packet delivered. Preview requests do not mark notes as used. Adapter tests distinguish unsupported acknowledgment from failed acknowledgment. Latency and packet overhead are recorded against the current baseline.

**Dependencies.** Packet contracts and budget selection from phase 3 precede adapter expansion. Generation and instance scoping must ship with post-compaction restoration, not as a later race fix.

## Phase 5 Control reuse and explain decisions

### Work item 12 Add explicit reuse and export policy

**Change.** Introduce optional note/project policy for project-only reuse, approved broader reuse, and export restrictions. First define the exact semantics in the note schema and shared eligibility function; then enforce them consistently in search expansion, synthesis, hubs, packet composition, and archive/export selection. Preserve legacy behavior for unclassified existing notes during migration and expose those notes as unclassified. Do not silently infer that old notes are public or private.

Project aliases should be explicit configuration resolving stable identities. Keep existing worktree-aware project discovery. Detect ambiguous aliases before broad reuse rather than requiring every vault to undergo an identity migration.

Promoting a project lesson to reusable knowledge should produce a reviewable draft with its project-specific details removed and its lineage retained. Derived material inherits the most restrictive source reuse policy until explicitly reviewed. Extend existing archive manifests and tombstone behavior to carry the policy; avoid a second export format.

**Boundary.** This is a memory reuse policy for the existing single-owner system. Project filtering is not an authorization boundary, and a shared owner credential does not provide tenant isolation. A multiuser ACL system would require a separate design covering authentication, storage access, indexing, logs, and export.

**Acceptance.** Restricted notes cannot leak through a derived hub or synthesis when the policy is enabled. Explicit broader reuse is inspectable and reversible. Legacy clients preserve unfamiliar policy metadata. Export previews identify exclusions and incomplete classification. Policy changes invalidate relevant caches.

### Work item 13 Add context preview and explanation

**Change.** Extend existing health and retrieval diagnostics with a read-only packet preview. Show source references and revisions, why each piece was selected or omitted, eligibility failures, source freshness, verification limits, budget estimates, and delivery state when known. Include profile and adapter capability versions so a support report can distinguish configuration from unsupported behavior.

Keep the default view compact; allow expansion into source and selection details. Report malformed profile references, stale derived notes, conflicting project aliases, and missing host events with specific repair actions. Preview should use the same composition code as actual delivery.

**Acceptance.** Preview does not update access counts, durability, delivery deduplication, or resurfacing timestamps. The preview and delivered packet agree for the same source snapshot. Diagnostic output avoids exposing excluded note bodies. Evidence marked partially verified or unverifiable remains visibly distinct from verified evidence. Report supported, unsupported, and untested capabilities separately.

**Dependencies.** Implement the preview while developing phase 3; add delivery and policy details as phases 4 and 5 land. Policy enforcement relies on the shared eligibility boundary from phase 1.

## Phase 6 Prove usefulness and keep integrations consistent

### Work item 14 Extend evaluations from retrieval to behavior

**Change.** Extend the existing Rondo benchmark and deterministic evaluation infrastructure. For each representative task, define the lesson, triggering situation, expected observable action, prohibited regression, and outcome grader. Store sanitized fixture references and compact results in Almanac's test assets; let the runner own transcripts and raw execution evidence.

Run matched conditions: no memory, current Almanac delivery, proposed delivery, and irrelevant or stale memory controls. Pin task revisions, model/runtime settings, and tool capabilities. Use repeated trials for stochastic agent runs and report uncertainty rather than treating a single success as improvement. Use deterministic action, output, and ordering checks where possible; use human or model judgment only where the rubric requires it and label those results separately.

Initial scenarios:

- A known project constraint changes an implementation choice correctly.
- A command lesson preserves its precondition under a tight packet budget.
- A superseded or invalidated note is excluded despite high search similarity.
- Source evidence changes while the synthesis source-name set remains unchanged.
- Compaction removes earlier context and the recovery packet restores the applicable lesson.
- An irrelevant or maliciously phrased note does not redirect the task.
- Concurrent delivery and compaction cannot suppress the new epoch's recovery.
- Restricted project knowledge cannot reach a broader derived packet.
- A stale write receives a revision conflict and preserves both authors' work.

**Metrics.** Task success and constraint violations are primary. Also report retrieval precision, unsupported-claim rate, unnecessary injections, packet size, time to first useful context, total latency, and maintenance cost. Reference overlap remains a retrieval signal; it is not evidence of causal improvement.

**Acceptance.** Deterministic regressions run in CI without live model credentials. Live-agent evaluations are explicit, repeatable runs with preserved evidence. Results report paired task differences and failure examples. New defaults require a predeclared non-regression gate for correctness and an agreed token/latency budget; choose numeric thresholds after measuring the baseline, before comparing candidate implementations.

### Work item 15 Generate shared integration contracts and validate installed artifacts

**Change.** Define a canonical home for shared schema descriptions and examples, with explicit host overlays for different tool names and lifecycle capabilities. Generate only genuinely shared fragments. Correct `project` versus `project_path` examples and document the additive lifecycle, revision, section, and policy contracts.

Extend current schema/tool-inventory drift checks to validate examples and generated fragments. Provide generation check/dry-run modes. Preserve installer hash protection, three-way merging, side files, and supported legacy aliases. Do not overwrite user-authored skills while distributing an update.

**Acceptance.** CI fails on stale generated fragments or schema-invalid examples. Packaged-install smoke tests exercise the actual distributed entry points, not just repository imports. Host overlays remain intentional and testable. A user-modified installed skill survives an upgrade. Update applicable CI and Beislið verification configuration explicitly so the new regression gates actually execute.

### Work item 16 Offer an optional OpenRig bridge after the core is stable

**Change.** If OpenRig becomes an actual host requirement, implement a thin adapter against Almanac's versioned memory-provider contract. It requests context at supported session boundaries and submits curated, sanitized lessons after work. It can pass canonical references and revisions into OpenRig context composition without copying the vault into its runtime state.

Keep OpenRig optional: no daemon, seat, scheduler, or workspace model becomes an Almanac core dependency. Validate the bridge with the same conformance scenarios as Pi, MCP, and CLI. Document unsupported acknowledgments and host events instead of simulating them.

**Acceptance.** Almanac installs and runs without OpenRig. Adapter failures do not corrupt notes or block unrelated host work. Native integration tests demonstrate the claimed lifecycle events. Do not implement this item merely to make the roadmap complete; a concrete integration need and passing core contracts are its entry criteria.

## Delivery sequence and review boundaries

These are reviewable implementation slices, not calendar estimates. Split further where a change crosses independent ownership boundaries.

1. **Regression fixtures and merge repair:** preserve metadata, stop invalidated/cross-project merge candidates, and verify certainty/provenance behavior. Work items 1–2 begin here.
2. **Shared eligibility:** apply the same rules to hubs, Inception, cached retrieval, and automatic delivery; retain explicit historical inspection. Finish work item 2.
3. **Revision contract:** optional compare-and-swap writes, semantic fingerprints, and cache freshness. Work item 3.
4. **Derived knowledge repair:** version the synthesis ledger, detect changed/removed sources, and expose bounded review/refresh. Work item 5.
5. **Evidence schema and verification:** preserve rationale and report evidence status accurately. Work items 4 and 6.
6. **Safe source references:** section reads and source-revision envelopes. Work item 7.
7. **Composer and preview:** whole-piece selection, budget diagnostics, and pure previews. Work items 8 and 13.
8. **Profiles:** built-in context views, then validated user/repository configuration. Work item 9.
9. **Lifecycle generation protocol:** host-instance/epoch state and race tests before adapter rollout. Work item 11.
10. **Adapter recovery:** situation-aware context, starting with a host that exposes compaction explicitly. Work item 10.
11. **Reuse policy:** opt-in classification, propagation, promotion drafts, and export enforcement. Work item 12.
12. **Default-selection decision:** use paired behavioral evaluations to decide which improvements become automatic. Work item 14.
13. **Optional bridge:** implement only for a real OpenRig deployment. Work item 16.

Evaluation fixtures from work item 14 and contract/documentation checks from work item 15 accompany every relevant slice. They are not deferred until the end. Evidence schema work can proceed alongside revision work, but source-refresh logic depends on fingerprints. Reuse policy depends on consistent eligibility and lineage. Post-compaction delivery depends on both bounded composition and generation-safe bookkeeping.

## Rollout and migration

### Stage A Correctness foundations

Ship merge preservation and invalidation exclusion as bug fixes with focused regression coverage. Inventory existing notes for missing provenance and suspicious synthesis before offering any repair. Preserve originals and produce a dry-run report. A missing citation cannot be reconstructed by guessing. Never perform a blanket rewrite of all notes as part of normal startup.

Use schema-versioned runtime records and backward-compatible optional note fields. Existing synthesis ledgers without hashes are unknown-freshness records; refresh them in bounded batches. Existing clients lacking revision support keep legacy behavior, but diagnostics must distinguish them from clients using conflict protection.

### Stage B Shadow composition

Compute candidate packets on a bounded sample without injecting them or incrementing usage/durability. Compare source selection, complete-piece retention, sizes, and latency against current delivery. Redact diagnostic bodies where required. Shadow mode must not double-run capture or maintenance.

### Stage C Opt-in host canary

Enable the new composer and recovery protocol for one capable host and a test vault. Exercise fresh, resume, compaction, restart, concurrent requests, and failure recovery. Confirm correct scope and source validity before testing a real project. Expand hosts individually as their capability contracts pass.

### Stage D Measured defaults

Enable new defaults only after deterministic tests and paired behavioral evaluations pass their predeclared gates. Keep custom profiles, broader reuse, and automatic promotion opt-in initially. Measure whether existing advanced features already solve a case before adding another mechanism.

### Rollback

Keep a configuration switch for legacy composition and host recovery delivery during rollout. Disabling new delivery must not discard note metadata or bypass integrity fixes. Runtime-state migrations need backup/rebuild behavior; raw notes remain authoritative. Profile and policy schema versions should reject unsupported semantics explicitly. Revision conflicts must never silently retry as unconditional overwrites. Archive/restore remains the recovery path for user-approved note changes.

## Release checklist

- Existing metadata and source evidence survive merge, replace, capture retries, archive, and restore.
- Invalidated knowledge is excluded from automatic delivery and derivation, including cache hits; historical inspection remains possible.
- Changed source contents trigger freshness review even when source identities are unchanged.
- Revision conflicts preserve the existing note and produce an actionable response.
- Budget fitting preserves conditions, rationale, and required dependencies or clearly reports their omission.
- Preview is read-only and matches delivery for the same snapshot.
- Compaction recovery is correctly scoped and survives deterministic concurrency/failure scenarios.
- Source verification reports its actual limits; anchor presence is not described as proof of semantic truth.
- Policy propagation blocks disallowed derived reuse without claiming multiuser isolation.
- Legacy tools and installed integrations pass compatibility checks.
- CI includes the new deterministic regression gates; live-agent evidence supports any default change.
- Operational diagnostics expose latency, incomplete packets, stale sources, and unsupported host capabilities without leaking excluded content.

## Decisions to settle during implementation

Default to lightweight Markdown-compatible metadata and a small built-in profile set. Finalize field spelling and schema versions with the first contract change. Select the section-address syntax after testing Unicode headings, repeated headings, and edited documents; avoid inheriting OpenRig's ASCII slug assumptions. Decide whether a stale derived note is suppressed or shown with a warning based on its use: automatic instructions deserve stricter handling than historical inspection.

Measure current latency and task outcomes before setting numerical release thresholds. Decide automatic refresh versus review-only synthesis per installation, with existing opt-in automation settings respected. Decide the first canary host based on available native tests; Pi has a visible compaction integration, but that alone does not prove every recovery event is reliable.

## Deliberate exclusions

Do not add an orchestration daemon, session/task tracker, general workflow language, marketplace, replacement search stack, or new archive format to implement this roadmap. Do not store raw transcripts as curated memory. Do not make every note satisfy a large taxonomy. Do not add arbitrary executable verification commands from note content. Do not build multiuser access control under the name of project scoping. These expand the product beyond the improvements supported by this comparison.

OpenRig's mechanisms are useful design references, not a guarantee of production readiness. Its refocus concurrency tests expose races, some adapter contracts describe proposed capabilities, and its source resolver can report a symlink escape rather than prevent the read. Adapt the useful concepts with Almanac's own safety boundaries and tests. Inspect license and attribution requirements before copying implementation code; the proposed roadmap primarily calls for native adaptations.

## OpenRig source references

All references below are pinned to the reviewed revision.

- [Architecture](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/ARCHITECTURE.md): context composition, ownership, and evaluation structure.
- [Profile composer](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/packages/daemon/src/domain/context-packs/profile-composer.ts): lifecycle selection, prerequisite closure, and budget reporting. Its budget report is not itself a trimming implementation.
- [Markdown addressing](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/packages/daemon/src/domain/markdown-address.ts): section-based source resolution and ambiguity handling.
- [Source resolver](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/packages/daemon/src/domain/context-packs/profile-source-resolver.ts): roots and provenance, with the symlink limitation noted above.
- [Knowledge maturity](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/docs/reference/knowledge-maturity.md): separate evidence, placement, and lifecycle concepts; these are conventions, not proof of enforced semantics.
- [Lore routing](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/docs/reference/lore-routing.md): situation, habitual mistake, better action, rationale, and reviewed promotion.
- [Refocus channel](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/docs/reference/refocus-channel.md): delivery deadlines, failure behavior, and event handling.
- [Evaluation system](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/packages/test-system/evals/README.md): executable behavioral probes and deterministic grading.
- [Harness runner contract](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/docs/reference/harness-runner-contract.md): explicit adapter capabilities and qualification boundaries.
- [Skill mirroring](https://github.com/mvschwarz/openrig/blob/bf350515376767ffb1bb1edea429e7bdf1a17c6a/scripts/mirror-skills.mjs): canonical sources and generated integration assets.
