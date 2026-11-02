---
title: Almanac OpenRig roadmap handoff for extended 6.1 Sol implementation
type: decision
tags: ["openrig", "roadmap", "handoff", "memory-integrity"]
source: mcp
origin: mcp_store
certainty: 4
validity-context: Planning handoff recorded 2026-11-02; implementation not started. Revalidate repository state before continuing.
project: almanac
date: 2026-11-02T00:24
---

User requested an extended OpenRig comparison, then an extensive improvement roadmap, and plans a fresh session with 6.1 Sol for multi-hour/day implementation. More than five minutes of substantive source review and isolated probes completed. No implementation, commits, or PRs were made.

Read the complete 16-work-item roadmap first: /root/work/AndriGitDev/almanac/docs/history/plans/2026-11-02-openrig-inspired-memory-improvements.md (5,222 words). IMPORTANT: docs/history/plans/ is ignored by the repository's plans/ gitignore rule, so this document is local and will not automatically follow a new checkout. Preserve or explicitly track the plan before worktree/machine changes.

Reviewed Almanac HEAD 874326d47a50ac59496c38c109deb196cbc46a02 and OpenRig bf350515376767ffb1bb1edea429e7bdf1a17c6a (https://github.com/mvschwarz/openrig). The roadmap has pinned source references, interfaces, dependencies, acceptance criteria, rollout and rollback.

Sequence: (1) preserve metadata and constrain merge candidates; (2) shared invalidation/eligibility across retrieval, caches, hubs and Inception; (3) optional revision-conflict writes plus semantic fingerprints; (4) source-aware synthesis refresh; (5) evidence/rationale schema and honest verification statuses; (6) safe section references; (7) complete-piece budget composer and pure preview; (8) named profiles/progressive disclosure; (9) host-instance/context-epoch protocol and race tests; (10) fresh/resume/post-compaction adapter delivery; (11) explicit reuse/export policy with inherited restrictions; (12) measured default changes using paired behavioral evaluation. Shared schema/example generation and installed-artifact tests accompany each slice. Optional OpenRig bridge only if a real integration need emerges.

Keep Markdown authoritative and extend existing search, archive, health, installer and benchmark infrastructure. Hosts own active tasks and conversations; runner owns raw evaluation evidence; runtime queues/caches stay outside curated knowledge. Project scope is not a multiuser ACL. No orchestration daemon or replacement search stack is needed.

First implementation action: inspect current instructions/status, recover this plan, establish test dependencies, add regression fixtures and repair metadata preservation plus invalidated/cross-project merge selection. Selected pytest run previously failed immediately because .venv/bin/python lacks pytest; isolated Python probes succeeded. Do not claim full tests passed. Implement reviewable slices with tests and checkpoints; avoid a single unbounded rewrite. Roll out integrity fixes first, then pure shadow composition, one-host canary, and measured defaults. User has not requested starting implementation in this capture turn.

## Related

