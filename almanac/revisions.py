"""Raw concurrency tokens and semantic freshness tokens for Markdown sources."""

import hashlib
import re
from pathlib import Path

from almanac.frontmatter import split_frontmatter

TELEMETRY_FIELDS = {"resurfaced_count", "last_resurfaced", "access_count", "last_accessed"}


def raw_revision(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return "sha256:" + hashlib.sha256(data).hexdigest()


def semantic_revision(text: str) -> str:
    fm, body = split_frontmatter(text)
    stable = fm
    for key in TELEMETRY_FIELDS:
        stable = re.sub(rf"^{key}:[^\n]*(?:\n[ \t]+[^\n]*)*(?:\n|$)", "", stable, flags=re.MULTILINE)
    stable = stable.strip()
    return raw_revision(f"{stable}\n---\n{body.strip()}")


def source_revisions(path: Path) -> dict:
    raw = path.read_bytes()
    return {"revision": raw_revision(raw), "semantic_revision": semantic_revision(raw.decode("utf-8"))}


class RevisionConflict(ValueError):
    def __init__(self, expected: str, actual: str):
        super().__init__("Source changed since it was read; reread and reconcile before retrying")
        self.details = {
            "error": str(self),
            "reason": "revision_conflict",
            "expected_revision": expected,
            "actual_revision": actual,
        }


def require_revision(text: str, expected: str | None) -> None:
    if expected is not None and expected != raw_revision(text):
        raise RevisionConflict(expected, raw_revision(text))


def stamp_results(vault: Path, results: list[dict]) -> list[dict]:
    """Attach semantic snapshots to a bounded cache result set."""
    for result in results:
        try:
            path = (vault / result["path"]).resolve()
            path.relative_to(vault.resolve())
            result["_source_semantic_revision"] = source_revisions(path)["semantic_revision"]
        except (OSError, ValueError, KeyError, UnicodeError):
            pass
    return results


def results_fresh(vault: Path, results: list[dict]) -> bool:
    for result in results:
        try:
            path = (vault / result["path"]).resolve()
            path.relative_to(vault.resolve())
            actual = source_revisions(path)["semantic_revision"]
            if actual != result.get("_source_semantic_revision"):
                return False
        except FileNotFoundError:
            if result.get("_source_semantic_revision"):
                return False
        except (OSError, ValueError, KeyError, UnicodeError):
            if result.get("_source_semantic_revision"):
                return False
    return True


def repair_sources(vault: Path, backend, state: dict, *, limit: int = 100) -> dict:
    """Bounded round-robin hash repair; detects edits with preserved mtimes.

    The caller persists this small cursor with existing maintenance state.
    Hashes are read on demand; only existing index_note is used for repair.
    """
    paths = sorted((vault / "notes").glob("*.md"))
    cursor = int(state.get("revision_cursor", 0)) % max(1, len(paths))
    checked = repaired = 0
    revisions = state.setdefault("source_revisions", {})
    for index in range(min(max(0, limit), len(paths))):
        path = paths[(cursor + index) % len(paths)]
        rel = str(path.relative_to(vault))
        try:
            revision = raw_revision(path.read_bytes())
            checked += 1
            if revisions.get(rel) != revision:
                if backend.index_note(rel):
                    revisions[rel] = revision
                    repaired += 1
        except OSError:
            continue
    state["revision_cursor"] = (cursor + checked) % max(1, len(paths))
    return {"checked": checked, "repaired": repaired}
