"""Opt-in memory reuse policy for a single owner, not a multiuser ACL."""

from almanac.config import get_config
from almanac.store import _derive_project_fields


def project_identity(value, config=None) -> str | None:
    config = get_config() if config is None else config
    slug, _ = _derive_project_fields(value)
    aliases = config.get("project_aliases", {})
    normalized = {}
    for alias, canonical in aliases.items():
        key, _ = _derive_project_fields(alias)
        target, _ = _derive_project_fields(canonical)
        if key in normalized and normalized[key] != target:
            raise ValueError("Ambiguous project alias")
        normalized[key] = target
    seen = set()
    while slug in normalized:
        if slug in seen or len(seen) >= 8:
            raise ValueError("Cyclic project aliases")
        seen.add(slug)
        slug = normalized[slug]
    return slug


def reuse_decision(fields, *, project=None, purpose="context", config=None) -> dict:
    config = get_config() if config is None else config
    scope = fields.get("reuse_scope") or "unclassified"
    export = fields.get("export_policy") or "unclassified"
    decision = {"allowed": True, "classification": scope, "export_policy": export, "reason": "legacy-or-approved"}
    if not config.get("reuse_policy_enabled", False):
        return {**decision, "reason": "policy-disabled"}
    if not isinstance(scope, str) or not isinstance(export, str):
        return {**decision, "allowed": False, "reason": "unsupported-policy"}
    if scope not in {"unclassified", "project", "reusable"} or export not in {"unclassified", "allow", "deny"}:
        return {**decision, "allowed": False, "reason": "unsupported-policy"}
    if purpose == "export" and export == "deny":
        return {**decision, "allowed": False, "reason": "export-denied"}
    if scope == "project" and purpose not in {"history", "synthesis-input"}:
        try:
            own, target = project_identity(fields.get("project"), config), project_identity(project, config)
        except ValueError:
            return {**decision, "allowed": False, "reason": "ambiguous-project"}
        if not own or own != target:
            return {**decision, "allowed": False, "reason": "project-only"}
    return decision


def inherited_policy(sources: list[dict], config=None) -> dict:
    for source in sources:
        scope, export = source.get("reuse_scope"), source.get("export_policy")
        if scope is not None and (not isinstance(scope, str) or scope not in {"unclassified", "project", "reusable"}):
            raise ValueError("Unsupported inherited reuse policy")
        if export is not None and (not isinstance(export, str) or export not in {"unclassified", "allow", "deny"}):
            raise ValueError("Unsupported inherited export policy")
    restricted = [s for s in sources if s.get("reuse_scope") == "project"]
    projects = {project_identity(s.get("project"), config) for s in restricted}
    if restricted and (None in projects or len(projects) != 1):
        raise ValueError("Incompatible restricted source projects")
    result = {}
    if restricted:
        result = {"reuse_scope": "project", "project": next(iter(projects))}
    elif sources and all(s.get("reuse_scope") == "reusable" for s in sources):
        result["reuse_scope"] = "reusable"
    if any(s.get("export_policy") == "deny" for s in sources):
        result["export_policy"] = "deny"
    return result


def promotion_draft(source: dict, *, body: str, rationale: str) -> dict:
    """Produce a host-reviewed draft; never silently promote source knowledge."""
    if not body.strip() or not rationale.strip():
        raise ValueError("A sanitized draft body and review rationale are required")
    return {
        "schema": "almanac-promotion/v1",
        "status": "draft",
        "body": body,
        "rationale": rationale,
        "source_reference": source["reference"],
        "source_revision": source["revision"],
        "proposed_reuse_scope": "reusable",
        "export_policy": source.get("metadata", {}).get("export_policy", "unclassified"),
    }


def effective_fields(vault, fields, *, depth=0):
    """Derived content inherits source restrictions until explicitly reviewed."""
    from almanac.frontmatter import parse
    from pathlib import Path

    sources = fields.get("synthesized_from") or []
    if not sources or str(fields.get("reuse_reviewed", "")).lower() == "true":
        return fields
    if depth >= 8 or not isinstance(sources, list) or len(sources) > 100:
        return {**fields, "reuse_scope": "unsupported"}
    records = []
    root = Path(vault).resolve()
    for stem in sources:
        found = None
        for prefix in ("notes", "archive"):
            path = (root / prefix / f"{stem}.md").resolve()
            if root not in path.parents:
                return {**fields, "reuse_scope": "unsupported"}
            try:
                text = path.read_text(encoding="utf-8")
                found = effective_fields(root, parse(text)[0], depth=depth + 1)
                break
            except (OSError, UnicodeError):
                continue
        if found is None:
            return {**fields, "reuse_scope": "unsupported"}
        records.append(found)
    try:
        inherited = inherited_policy(records)
    except ValueError:
        return {**fields, "reuse_scope": "unsupported"}
    if any(row.get("reuse_scope") == "unsupported" for row in records):
        inherited["reuse_scope"] = "unsupported"
    return {**fields, **inherited}
