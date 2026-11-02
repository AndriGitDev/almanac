"""Compact, explicit evidence encoding; usage is never independent confirmation."""

import json

from almanac.frontmatter import get_scalar
from almanac.utils import sanitize_secrets

EVIDENCE_FIELDS = {"method", "summary", "applicability", "action", "invalidating_conditions"}
METHODS = {"observation", "code_check", "human_decision", "synthesis"}


def normalize_evidence(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("evidence must be an object")
    if set(value) - EVIDENCE_FIELDS:
        raise ValueError("Unknown evidence field")
    result = {}
    for key, text in value.items():
        if not isinstance(text, str) or len(text) > 2000:
            raise ValueError("Evidence fields must be strings of at most 2000 characters")
        result[key] = sanitize_secrets(text).strip()
    if result.get("method") and result["method"] not in METHODS:
        raise ValueError("Unsupported evidence method")
    return result


def read_evidence(frontmatter: str) -> dict:
    raw = get_scalar(frontmatter, "evidence")
    if not raw:
        return {}
    try:
        return normalize_evidence(json.loads(raw))
    except (ValueError, TypeError):
        return {"status": "malformed"}


def update_metadata(text: str, updates: dict | None) -> str:
    """Explicit optional-field updates; omission preserves, None removes."""
    if updates is None:
        return text
    import re
    from almanac.frontmatter import split_frontmatter

    allowed = {
        "evidence",
        "citations",
        "reuse_scope",
        "export_policy",
        "reuse_reviewed",
        "review_after",
        "invalidated_by",
    }
    if not isinstance(updates, dict) or set(updates) - allowed:
        raise ValueError("Unsupported explicit metadata update")
    fm, body = split_frontmatter(text)
    for key, value in updates.items():
        if key == "evidence" and value is not None:
            value = normalize_evidence(value)
        if key == "citations" and value is not None:
            from almanac.store import _normalize_citations

            value = _normalize_citations(value)
        if key == "reuse_scope" and value not in {None, "project", "reusable"}:
            raise ValueError("Unsupported reuse scope")
        if key == "export_policy" and value not in {None, "allow", "deny"}:
            raise ValueError("Unsupported export policy")
        fm = re.sub(rf"^{key}:[^\n]*(?:\n[ \t]+[^\n]*)*", "", fm, flags=re.MULTILINE)
        if value is not None:
            encoded = (
                json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list, bool))
                else str(value)
            )
            if "\n" in encoded or "\r" in encoded:
                raise ValueError("Metadata scalars must occupy one line")
            fm += f"\n{key}: {encoded}"
    return f"---\n{fm}\n---\n{body}"


def metadata_matches(text: str, *, evidence=None, citations=None, updates=None) -> bool:
    from almanac.frontmatter import split_frontmatter

    fm, _ = split_frontmatter(text)
    expected = dict(updates or {})
    if evidence:
        expected["evidence"] = evidence
    if citations:
        expected["citations"] = citations
    for key, value in expected.items():
        raw = get_scalar(fm, key)
        if value is None:
            if raw is not None:
                return False
            continue
        try:
            actual = json.loads(raw) if isinstance(value, (dict, list, bool)) else raw
        except (ValueError, TypeError):
            return False
        if actual != value:
            return False
    return True
