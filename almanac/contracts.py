"""Canonical additive context/evidence contract and portable integration examples."""

CONTRACT = {
    "schema": "almanac-contracts/v1",
    "context_schema": "almanac-context/v1",
    "profile_schema": "almanac-profiles/v1",
    "situations": ["fresh", "resume", "post_compaction"],
    "profiles": ["orientation", "debugging", "design-review", "recovery"],
    "request_fields": [
        "situation",
        "host_instance_id",
        "context_epoch",
        "profile",
        "preview",
        "acknowledge_packet_id",
        "delivery_outcome",
        "retry",
    ],
    "revision": {
        "raw": "sha256 of original bytes",
        "semantic": "claim and metadata excluding resurfacing/access telemetry",
        "conditional_write": "expected_revision; conflict never retries unconditionally",
    },
    "evidence": {
        "encoding": "single-line JSON object",
        "fields": ["method", "summary", "applicability", "action", "invalidating_conditions"],
        "methods": ["observation", "code_check", "human_decision", "synthesis"],
        "verification": ["verified", "partial", "stale", "unverifiable", "no-citations", "disabled"],
        "meaning": "Anchor presence is not semantic proof",
    },
    "policy": {
        "reuse_scope": ["project", "reusable"],
        "export_policy": ["allow", "deny"],
        "missing": "unclassified; legacy behavior until policy enabled",
        "boundary": "single owner reuse policy, not a multiuser ACL",
    },
    "note_example": {
        "title": "Retain cache ownership preconditions",
        "type": "decision",
        "project": "almanac",
        "project_path": "/path/to/almanac",
        "certainty": 4,
    },
    "adapters": {
        "cli": {
            "fresh": "explicit",
            "resume": "explicit",
            "post_compaction": "explicit",
            "acknowledgment": "explicit-host-report",
        },
        "mcp": {
            "fresh": "explicit",
            "resume": "explicit",
            "post_compaction": "explicit",
            "host_identity": "caller-supplied",
            "acknowledgment": "explicit-host-report",
        },
        "pi": {
            "fresh": "session_start",
            "resume": "subsequent current-intent request",
            "post_compaction": "session_compact; next before_agent_start",
            "acknowledgment": "unsupported",
            "live_sdk_canary": "not-run",
        },
        "legacy_hooks": {"context_epochs": "unsupported", "behavior": "legacy delivery retained"},
    },
}


def integration_fragment(tool_prefix="almanac") -> str:
    return f"""<!-- almanac-context-contract:start -->
Shared contract: `almanac-context/v1` (generated from `almanac/contracts.py`).

Use `{tool_prefix}_search` and `{tool_prefix}_get` for explicit recall. Known-note
reads accept exact sections such as `notes/cache-policy.md#applicability` and
return source revisions and validity. Anchor checks verify text presence only.

Note identity uses `project: almanac` and optional
`project_path: /path/to/almanac`; a path is not a project slug.
Keep applicability, recommended action and rationale together. Optional
`evidence` is a single-line JSON object; never invent evidence or treat access
counts as confirmation. Merges preserve original provenance and confidence.

Hosts may opt into `{tool_prefix}_session_context` with `situation`,
`host_instance_id`, `context_epoch` and `profile`. `preview: true` is read-only.
The host owns live tasks and compaction generations. Restricted reuse is
opt-in and does not provide multiuser authorization.
<!-- almanac-context-contract:end -->"""


def optional_context_arguments(**arguments):
    defaults = {
        "situation": None,
        "host_instance_id": None,
        "context_epoch": None,
        "profile": None,
        "preview": False,
        "acknowledge_packet_id": None,
        "delivery_outcome": "attached",
        "retry": False,
    }
    return {key: value for key, value in arguments.items() if value != defaults[key]}
