# Memory integrity and context delivery

Almanac keeps Markdown authoritative while adding source revisions, evidence-aware
maintenance, exact section reads, and opt-in complete-piece context delivery. The
[versioned contract](contracts/context-v1.json) is generated from
`almanac/contracts.py`. Existing tools and Memento aliases remain available.

## Integrity and revision writes

`get` returns `revision` (SHA-256 of original bytes), `semantic_revision`, source
validity, evidence and anchor-verification status. Semantic revisions include
claims, conditions, citations, evidence and reuse policy, but exclude access
counters and resurfacing timestamps. Raw revisions deliberately include all
bytes, including telemetry updates.

`almanac_replace_note` accepts optional `expected_revision`. The comparison and
write share the reentrant vault lock, whose ownership includes the thread as
well as the process. A mismatch returns `reason: revision_conflict`, the expected
revision and the current revision, and leaves the file unchanged. Reread and
reconcile before retrying. A repeated stale precondition remains a conflict;
it never repeats an overwrite. Merge helpers support the same precondition.
Remote clients require advertised conditional-write support before replacement;
the sync conflict path uses the revision of the inspected remote candidate.
Older servers cannot silently downgrade the request to an unconditional write.

Append-merges preserve the original origin, confidence, citations, conditions,
project identity, unknown fields and multiline metadata. Incoming evidence is
scoped to its appended section. Matching text with different evidence is not
silently discarded as a retry. Replacement cues, conflicting polarity and
incompatible note types take the review path. These conservative checks do not
claim to solve arbitrary semantic contradiction detection.

Optional `metadata_updates` on store/replace distinguish an omitted field from
an explicit `null` removal. Supported fields are `evidence`, `citations`,
`reuse_scope`, `export_policy`, `reuse_reviewed`, `review_after`, and
`invalidated_by`. Existing unfamiliar fields survive replacement.

## Evidence and source maintenance

Optional `evidence` uses one single-line JSON object. Its fields are `method`,
`summary`, `applicability`, `action`, and `invalidating_conditions`; each supplied
string is bounded to 2,000 characters. Methods are `observation`, `code_check`,
`human_decision`, and `synthesis`. Capture retains situation/action/rationale and
caveats without inventing support. Access counts are usage signals.

Anchor status is `verified`, `partial`, `stale`, `unverifiable`, `no-citations`, or
`disabled`. A verified substring is evidence of anchor presence, not proof of
claim truth. A bounded file read without a match is partial when the unread
suffix could contain the anchor. Missing files or repository context remain
unverifiable. An optional `review_after` date creates a review reminder; age
alone never invalidates a claim. Incoming section-scoped citations are retained;
the current note-level verifier does not pretend to check those automatically.

The existing sweeper performs a bounded round-robin hash repair using the
existing indexer, detecting out-of-band edits even when timestamps were
preserved. Runtime cursors, reverse dependencies and derived-review candidates
live outside the curated vault. Review inventory is also available read-only:

```sh
almanac source-review --limit 100 --cursor 0
```

Inception records `synthesized_revisions` alongside `synthesized_from`. Changed
content under an unchanged filename now reaches incremental refresh. Sources
are reread after contradiction adjudication and checked again before publication;
refresh also compares the prior pattern revision. Legacy ledgers without hashes
have unknown freshness and enter the existing bounded refresh budget. Failed
refreshes preserve the previous note. Archived provenance remains resolvable;
archival refuses to overwrite different evidence already at the destination.
Known changed/invalidated evidence is excluded from automatic current guidance.
Unavailable sources create a visible review gap rather than proving a claim false.

## Exact references

CLI, MCP and composition share one resolver:

```sh
almanac get notes/cache-policy.md#applicability
```

Addresses use NFKC-normalized, case-folded heading slugs. Unicode letters and
numbers, underscores and hyphens survive; whitespace becomes hyphens and other
punctuation is removed. ATX headings (`#` through `######`) are supported.
A section includes child headings until the next peer or ancestor. Code-fence
and HTML-comment headings are ignored. Duplicate normalized headings are
ambiguous, with no implicit numeric suffix. Missing sections, malformed fences,
missing files and denied roots have distinct errors. A section never falls back
to a fuzzy match. Traversal and symlink escapes are rejected before reading.
Full-note reads keep their legacy fallback behavior. Section envelopes retain
source revisions, validity and evidence metadata.

## Composer, profiles and preview

The new composer is opt-in with `context_composer_enabled: true`; an explicit
profile, situation or preview request also selects the versioned path. Existing
no-profile calls retain legacy behavior for rollback. Built-in views are
`orientation`, `debugging`, `design-review`, and `recovery`, using existing search
candidates with view-specific priorities. A host supplies current intent;
Almanac does not reconstruct active tasks from old notes.

```sh
almanac context-preview --cwd /path/to/almanac --prompt 'debug cache expiry' --profile debugging
```

Preview shares the delivery composer but does not update access counters,
resurfacing, durability or delivery state. It explains selected references,
revisions, evidence limits, priorities, dependency omissions, budgets and adapter
capabilities. Excluded bodies do not enter diagnostic output. Shadow comparison
uses this command against a bounded set of representative requests.

Configure user profiles in `context_profiles` or repository profiles in
`.almanac/context-profiles.json`:

```json
{
  "schema": "almanac-profiles/v1",
  "profiles": {
    "cache-review": {
      "pieces": [
        {"reference": "notes/cache-policy.md#applicability", "priority": 100},
        {"reference": "notes/cache-policy.md#action", "priority": 90,
         "required": true, "requires": ["notes/cache-policy.md#applicability"]}
      ]
    }
  }
}
```

Profiles are bounded to 32 pieces, eight prerequisites per piece and depth
eight. Cycles, undefined prerequisites, repeated references and unsupported
versions fail explicitly. Repository configuration is bounded to 64 KB.

A complete note/section, its caveats and evidence labels form one indivisible
piece. Prerequisite groups fit together or are omitted together. Selected-piece
metadata uses offsets into `content`, avoiding duplicate large text. Budgets use
an explicitly labeled characters/4 token estimate for content; envelope overhead
is separate. Tiny budgets produce empty/incomplete content with bounded omission
reasons. No model call is added to normal composition. The opted-in prompt,
tool-context and Pi adapter paths consume these complete pieces without a final
character slice. The source revisions are checked again before returning a packet.

## Host generations and recovery

```sh
almanac session-context --cwd /path/to/almanac --session-id session-1 \
  --situation post_compaction --host-instance-id host-unique-id --context-epoch 2
```

Situations are `fresh`, `resume` and `post_compaction`. Recovery requires a host
instance and nonnegative epoch. Scope includes vault, host instance, checkout,
project, session and epoch. Increase the epoch after compaction. The host keeps
conversation/task/handoff state; none becomes curated memory automatically.

Bookkeeping distinguishes preparation, return to the caller and an optional
host-reported acknowledgment. Atomic publication with a stable lock file rejects
old in-flight epochs and stale acknowledgments, including after restart. A
returned packet does not prove attachment or model usage. Same-epoch repeats are
suppressed; explicit `retry` permits recovery after an uncertain return.
`acknowledge_packet_id` with `delivery_outcome: attached|failed` records a caller
report. Failed reports retain retryability. Corrupt/unavailable state produces
an actionable failure rather than silently erasing generations.

Pi opts in with `ALMANAC_PI_CONTEXT_COMPOSER=true` (or `contextComposer` in its
existing bridge configuration). It keeps a process instance and generation,
advances at `session_compact`, and requests recovery at the next
`before_agent_start`. It discards a pre-compaction response still in flight.
Real adapter handlers are tested against a mocked host event API using Node 24
native TypeScript loading; the portable JS generation tests also run on Node 20.
A live SDK/model canary is not claimed. Pi attachment acknowledgment is
unsupported; CLI/MCP expose explicit host reports. Legacy hooks retain their
existing lifecycle behavior and do not claim compaction-event support.

## Reuse and exports

Enable enforcement explicitly with `reuse_policy_enabled: true`. Notes may set
`reuse_scope: project|reusable` and `export_policy: allow|deny`. Missing fields
remain inspectably unclassified with legacy behavior; no migration guesses that
old notes are public or private. `project_aliases` maps explicit aliases to stable
identities and rejects ambiguous/cyclic mappings.

Derived content inherits the most restrictive source policy until explicitly
reviewed. Incompatible restricted projects cannot be synthesized together.
Search expansion, hubs, packet composition and exports enforce inherited
restrictions. Legacy hubs without provenance are excluded under enforcement
until rebuilt. This is a single-owner reuse policy, not tenant isolation or ACLs.

A promotion is a draft containing a host-authored sanitized body, review
rationale and source lineage:

```sh
almanac promotion-draft notes/cache-policy.md --body-file sanitized-draft.md \
  --rationale 'Reviewed project-specific assumptions for broader reuse'
almanac archive export output.zip --preview --project almanac
```

The draft does not change source policy. An owner can apply reviewed metadata
explicitly; setting `reuse_reviewed: true` makes that decision inspectable and
reversible. Export preview lists exclusions and incomplete classification. The
portable archive format retains note metadata and filters denied bodies, derived
hubs, relevant tombstones and runtime sync ledgers under enforcement. Its manifest
records exclusion counts rather than denied source references.

## Evaluation and defaults

Run `python evals/run_evals.py --suite context_behavior` for hermetic matched
policy controls. `benchmark/rondo/behavior.py` grades observable expected actions
and prohibited regressions, requiring matched task revision, runtime, model and
tool pins across no-memory/current/proposed/irrelevant-or-stale conditions.
It reports paired differences and uncertainty separately from retrieval overlap.
A single outcome/reference match cannot establish causal memory contribution.

The deterministic fixture demonstrates complete-piece safety and bounded output;
it is not a stochastic agent study. New composer, profiles and broader reuse
remain opt-in. Live-agent repeated trials and a host canary are required before
changing those defaults. Raw transcripts and execution evidence remain runner-
owned; Almanac keeps compact fixtures and sanitized results. The optional OpenRig
bridge remains gated on a concrete deployment need, as the original plan requires.
