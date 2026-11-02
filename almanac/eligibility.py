"""Shared validity boundary for current guidance, derivation and merge writes.

Missing optional metadata keeps legacy read behavior. Merge writes require
matching project identities, including unscoped notes: similarity alone cannot
authorize moving evidence between projects. Historical inspection is explicit.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from almanac.store import _derive_project_fields

Purpose = Literal["context", "synthesis", "merge", "history"]


def note_eligible(fields: Mapping, *, purpose: Purpose, project: str | None = None) -> bool:
    if purpose not in {"context", "synthesis", "merge", "history"}:
        raise ValueError(f"Unknown eligibility purpose: {purpose}")
    if purpose == "history":
        return True
    invalidated = fields.get("invalidated_by")
    if invalidated and str(invalidated).strip():
        return False
    if purpose == "merge":
        existing, _ = _derive_project_fields(fields.get("project"))
        incoming, _ = _derive_project_fields(project)
        return existing == incoming
    return True


def filter_eligible_results(
    vault: Path, results: list[dict], *, purpose: Purpose = "context"
) -> tuple[list[dict], int]:
    """Recheck bounded result sets against current Markdown before use.

    Unavailable local/remote metadata retains legacy fail-open reads. A known
    invalidation in the result or current file always excludes it. No cached
    metadata can override current invalidation. Merge targets use stricter
    existence, parsing and project checks in the write path.
    """
    from almanac.query import read_note_record

    kept = []
    for result in results:
        snapshots = [result, result.get("_meta") or {}]
        try:
            record = read_note_record(vault, result.get("path", ""))
        except (OSError, ValueError):
            record = None
        if record is not None:
            snapshots.append(record)
        if all(note_eligible(fields, purpose=purpose) for fields in snapshots):
            kept.append(result)
    return kept, len(results) - len(kept)
