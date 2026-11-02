"""Shared validity boundary for current guidance, derivation and merge writes.

Missing optional metadata keeps legacy read behavior. Merge writes require
matching project identities, including unscoped notes: similarity alone cannot
authorize moving evidence between projects. Historical inspection is explicit.
"""

from collections.abc import Mapping
from typing import Literal

from almanac.store import _derive_project_fields

Purpose = Literal["context", "synthesis", "merge", "history"]


def note_eligible(fields: Mapping, *, purpose: Purpose, project: str | None = None) -> bool:
    if purpose not in {"context", "synthesis", "merge", "history"}:
        raise ValueError(f"Unknown eligibility purpose: {purpose}")
    if purpose == "history":
        return True
    if fields.get("invalidated_by"):
        return False
    if purpose == "merge":
        existing, _ = _derive_project_fields(fields.get("project"))
        incoming, _ = _derive_project_fields(project)
        return existing == incoming
    return True
