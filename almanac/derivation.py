"""Source-aware synthesis freshness and bounded maintenance, outside prompt paths."""

import json
from pathlib import Path

from almanac.frontmatter import parse, split_frontmatter, get_scalar
from almanac.references import SourceError, read_reference


class SourceSet(set):
    """Set-compatible ledger entry with explicit source freshness."""

    def __init__(self, sources, *, fresh: bool, revision=None):
        super().__init__(sources)
        self.fresh = fresh
        self.revision = revision


def source_snapshot(vault: Path, stems) -> dict[str, str]:
    snapshots = {}
    for stem in stems:
        source = read_reference(vault, f"notes/{stem}.md")
        if source["validity_status"] != "current":
            raise ValueError("Invalidated synthesis source")
        snapshots[stem] = source["semantic_revision"]
    return snapshots


def derived_status(vault: Path, text: str) -> dict:
    fields, _ = parse(text)
    sources = fields.get("synthesized_from") or []
    if not isinstance(sources, list) or not sources:
        return {"status": "not-derived", "sources": []}
    fm, _ = split_frontmatter(text)
    try:
        expected = json.loads(get_scalar(fm, "synthesized_revisions") or "{}")
    except (ValueError, TypeError):
        expected = {}
    if not isinstance(expected, dict):
        expected = {}
    outcomes = []
    for stem in sources[:100]:
        try:
            source = read_reference(vault, f"notes/{stem}.md")
            status = "current"
        except SourceError:
            try:
                source = read_reference(vault, f"archive/{stem}.md")
                status = "archived"
            except SourceError:
                outcomes.append({"source": stem, "status": "unavailable"})
                continue
        if source["validity_status"] == "invalidated":
            status = "invalidated"
        elif stem not in expected:
            status = "unknown"
        elif source["semantic_revision"] != expected[stem]:
            status = "changed"
        outcomes.append({"source": stem, "status": status})
    current = len(sources) <= 100 and all(row["status"] in {"current", "archived"} for row in outcomes)
    return {"status": "current" if current else "needs-review", "sources": outcomes}


def derived_review(vault: Path, *, limit: int = 100, cursor: int = 0) -> dict:
    """Read-only bounded inventory; caller persists review candidates outside vault."""
    paths = sorted((vault / "notes").glob("*.md"))
    reviews, reverse = [], {}
    chosen = (paths[cursor:] + paths[:cursor])[: max(0, limit)]
    for path in chosen:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        status = derived_status(vault, text)
        for source in status["sources"]:
            reverse.setdefault(source["source"], []).append(str(path.relative_to(vault)))
        if status["status"] == "needs-review":
            reviews.append({"path": str(path.relative_to(vault)), **status})
    return {
        "schema": "almanac-derived-review/v1",
        "reviews": reviews,
        "reverse_dependencies": reverse,
        "cursor": (cursor + len(chosen)) % max(1, len(paths)),
        "checked_paths": [str(path.relative_to(vault)) for path in chosen],
    }
