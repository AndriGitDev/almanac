"""Pure whole-source composition with bounded profiles and explicit prerequisites."""

import json
import math
from pathlib import Path

from almanac.derivation import derived_status
from almanac.eligibility import note_eligible
from almanac.frontmatter import split_frontmatter
from almanac.policy import reuse_decision, effective_fields
from almanac.references import SourceError, read_reference
from almanac.revisions import raw_revision, source_revisions

SCHEMA = "almanac-context/v1"
BUILTINS = {"orientation", "debugging", "design-review", "recovery"}
MAX_PIECES = 32


def profile_definition(name: str, *, config: dict, cwd: str = "") -> dict:
    profiles = dict(config.get("context_profiles", {}))
    path = Path(cwd) / ".almanac" / "context-profiles.json" if cwd else None
    if path and path.is_file():
        if path.stat().st_size > 64_000:
            raise ValueError("Profile configuration exceeds 64KB")
        document = json.loads(path.read_text())
        if not isinstance(document, dict) or not isinstance(document.get("profiles"), dict):
            raise ValueError("Invalid profile document")
        if document.get("schema") != "almanac-profiles/v1":
            raise ValueError("Unsupported profile schema")
        profiles.update(document.get("profiles", {}))
    if name in profiles:
        profile = profiles[name]
        if not isinstance(profile, dict) or set(profile) - {"pieces", "description"}:
            raise ValueError("Invalid profile definition")
        entries = profile.get("pieces", [])
        if not isinstance(entries, list) or len(entries) > MAX_PIECES:
            raise ValueError("A profile supports at most 32 pieces")
        seen = set()
        for row in entries:
            if not isinstance(row, dict) or set(row) - {"reference", "priority", "required", "requires"}:
                raise ValueError("Invalid profile piece")
            ref = row.get("reference")
            if not isinstance(ref, str) or len(ref) > 1000 or ref in seen:
                raise ValueError("Missing, repeated or oversized profile reference")
            seen.add(ref)
            if (
                not isinstance(row.get("requires", []), list)
                or len(row.get("requires", [])) > 8
                or any(not isinstance(ref, str) for ref in row.get("requires", []))
            ):
                raise ValueError("Invalid prerequisite list")
            if not isinstance(row.get("priority", 50), (int, float)) or not math.isfinite(row.get("priority", 50)):
                raise ValueError("Priority must be numeric")
        _validate_dependencies(entries)
        return {"name": name, "version": 1, "pieces": entries, "source": "configured"}
    if name not in BUILTINS:
        raise ValueError(f"Unknown context profile: {name}")
    return {"name": name, "version": 1, "pieces": [], "source": "builtin"}


def _validate_dependencies(entries):
    by_ref = {row["reference"]: row for row in entries}

    visited = set()

    def visit(ref, stack):
        if ref in stack or len(stack) >= 8:
            raise ValueError("Profile prerequisites contain a cycle or exceed depth 8")
        if ref in visited:
            return
        if ref not in by_ref:
            raise ValueError(f"Missing prerequisite definition: {ref}")
        for dep in by_ref[ref].get("requires", []):
            visit(dep, stack + [ref])
        visited.add(ref)

    for ref in by_ref:
        visit(ref, [])


def compose(
    vault: Path,
    candidates: list[dict],
    *,
    token_budget: int = 2000,
    profile: dict | None = None,
    project: str | None = None,
    config: dict | None = None,
) -> dict:
    """No writes, counters, delivery state, logs, LLM calls, or mutable inputs."""
    config = config or {}
    profile = profile or {"name": "orientation", "version": 1, "pieces": []}
    if not isinstance(token_budget, int) or token_budget < 0 or token_budget > 100_000:
        raise ValueError("token_budget must be between 0 and 100000")
    entries = [dict(row) for row in profile.get("pieces", [])]
    if not entries:
        seen = set()
        for result in candidates[:MAX_PIECES]:
            ref = result.get("reference") or result.get("path")
            if ref and ref not in seen:
                entries.append(
                    {
                        "reference": ref,
                        "priority": result.get("priority", 50 + 100 * float(result.get("score", 0))),
                        "required": False,
                    }
                )
                seen.add(ref)
    if len(entries) > MAX_PIECES:
        raise ValueError("Composition exceeds 32 pieces")
    _validate_dependencies(entries)
    by_ref = {row["reference"]: row for row in entries}
    available, failures = {}, {}
    for ref, entry in by_ref.items():
        try:
            source = read_reference(vault, ref)
            fields = effective_fields(vault, source["metadata"])
            if not note_eligible(fields, purpose="context", project=project):
                failures[ref] = "invalidated-or-ineligible"
                continue
            if (
                config.get("reuse_policy_enabled", False)
                and source["path"].startswith("projects/")
                and not fields.get("synthesized_from")
            ):
                failures[ref] = "legacy-hub-provenance-unclassified"
                continue
            if profile.get("source") == "builtin" and project and fields.get("project"):
                from almanac.policy import project_identity

                if project_identity(fields["project"], config) != project_identity(project, config):
                    failures[ref] = "project-mismatch"
                    continue
            policy = reuse_decision(fields, project=project, config=config)
            if not policy["allowed"]:
                failures[ref] = policy["reason"]
                continue
            # Derived evidence is resolved as a bounded per-source read, not a vault scan.
            raw = "---\n" + source["frontmatter"] + "\n---\n"
            freshness = derived_status(vault, raw)
            if freshness["status"] == "needs-review":
                failures[ref] = "derived-evidence-needs-review"
                continue
            if profile.get("source") == "builtin":
                kind = fields.get("type")
                name = profile["name"]
                weight = (
                    30
                    if (name == "debugging" and kind == "bugfix")
                    or (name in {"orientation", "design-review", "recovery"} and kind in {"decision", "architecture"})
                    else 0
                )
                if name == "recovery" and fields.get("pinned") == "true":
                    weight += 40
                entry["priority"] = entry.get("priority", 50) + weight
            content = source["content"]
            if "#" not in source["reference"]:
                _, content = split_frontmatter(content)
            # Keep caveats and evidence labels in the same indivisible piece.
            from almanac.lifecycle import strip_injection

            qualifications = []
            if fields.get("validity-context"):
                qualifications.append("Applicability: " + str(fields["validity-context"]))
            evidence = source.get("evidence", {})
            for key, label in [
                ("applicability", "Applicability"),
                ("action", "Recommended action"),
                ("summary", "Evidence/rationale"),
                ("invalidating_conditions", "Invalidating conditions"),
            ]:
                if evidence.get(key):
                    qualifications.append(label + ": " + str(evidence[key]))
            text = f"[vault evidence: {source['reference']}; anchor check: {source['verification']['status']} (not claim verification); review: {source['review_status']}]\n"
            text += strip_injection(content.strip())
            if qualifications:
                text += "\n\n" + strip_injection("\n".join(qualifications))
            available[ref] = {"text": text, "source": source, "policy": policy, "freshness": freshness}
        except SourceError as exc:
            failures[ref] = exc.reason
    selected, omissions = [], []
    used = 0

    closures = {}

    def closure(ref):
        if ref in closures:
            return closures[ref]
        group = []
        for dep in by_ref[ref].get("requires", []):
            for item in closure(dep):
                if item not in group:
                    group.append(item)
        if ref not in group:
            group.append(ref)
        closures[ref] = group
        return group

    for row in sorted(entries, key=lambda r: (-r.get("priority", 50), r["reference"])):
        ref = row["reference"]
        if ref in selected:
            continue
        group = closure(ref)
        broken = next((r for r in group if r in failures), None)
        reason = failures[broken] if broken else None
        fresh = [r for r in group if r not in selected]
        cost = (
            sum(len(available[r]["text"]) + (2 if selected or i else 0) for i, r in enumerate(fresh))
            if not broken
            else 0
        )
        if not broken and used + cost > token_budget * 4:
            reason = "dependency-group-exceeds-budget"
        if reason:
            omissions.append({"reference": ref, "reason": reason, "required": bool(row.get("required"))})
        else:
            selected.extend(fresh)
            used += cost
    changed = []
    for ref in selected:
        try:
            source = available[ref]["source"]
            if source_revisions(vault / source["path"])["revision"] != source["revision"]:
                changed.append(ref)
        except (OSError, UnicodeError):
            changed.append(ref)
    if changed:
        omissions.extend(
            {"reference": ref, "reason": "source-changed-during-composition", "required": True} for ref in changed
        )
        selected = []  # Never return half of a concurrently changed prerequisite group.
    text = "\n\n".join(available[ref]["text"] for ref in selected)
    pieces, offset = [], 0
    for ref in selected:
        piece, entry = available[ref], by_ref[ref]
        source = piece["source"]
        end = offset + len(piece["text"])
        pieces.append(
            {
                "reference": source["reference"],
                "revision": source["revision"],
                "semantic_revision": source["semantic_revision"],
                "rendered_hash": raw_revision(piece["text"]),
                "start": offset,
                "end": end,
                "estimated_tokens": math.ceil(len(piece["text"]) / 4),
                "purpose": profile["name"],
                "priority": entry.get("priority", 50),
                "requires": entry.get("requires", []),
                "verification": source["verification"],
                "validity_status": source["validity_status"],
                "review_status": source["review_status"],
                "policy": piece["policy"],
            }
        )
        offset = end + 2
    identity = json.dumps(
        {
            "profile": profile,
            "pieces": [{k: v for k, v in piece.items() if k != "revision"} for piece in pieces],
            "budget": token_budget,
        },
        sort_keys=True,
    )
    return {
        "schema": SCHEMA,
        "packet_id": raw_revision(identity),
        "should_inject": bool(text),
        "content": text,
        "results": [
            {"path": available[ref]["source"]["path"], "title": available[ref]["source"]["title"]} for ref in selected
        ],
        "pieces": pieces,
        "complete": bool(text) and not any(o["required"] for o in omissions),
        "metadata": {
            "profile": {k: profile[k] for k in ("name", "version", "source") if k in profile},
            "token_budget": token_budget,
            "used_chars": len(text),
            "estimated_tokens": math.ceil(len(text) / 4),
            "accounting": "content-characters/4 estimate; envelope excluded",
            "omissions": omissions[:20],
            "omitted_report_count": max(0, len(omissions) - 20),
            "expandable_paths": list(by_ref)[:32],
            "truncated": False,
        },
    }
