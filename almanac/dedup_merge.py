"""Capture-time dedup/merge via embedding similarity.

``find_merge_target`` checks if an incoming note is a near-duplicate of an
existing note (vector similarity above threshold).  ``merge_into_canonical``
appends incoming content and scoped provenance, unions tags, and preserves
canonical metadata and the access-log signal.
"""

from __future__ import annotations

import logging
import json
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from almanac.config import get_config, get_vault, slugify
from almanac import frontmatter
from almanac.store import (
    _render_note_markdown,
    _write_text_atomic,
    normalize_note_contract,
    acquire_vault_write_lock,
    owns_vault_write_lock,
    release_vault_write_lock,
    load_access_log_stats,
    write_access_log_stats,
)
from almanac.eligibility import note_eligible

logger = logging.getLogger(__name__)

# Sentinel section marker used in merged notes.
_MERGED_SECTION_HEADER = "## Merged from"


@dataclass
class MergeTarget:
    """A canonical note that an incoming note should be merged into."""

    path: str  # vault-relative path like "notes/redis-cache-guidance.md"
    similarity: float
    title: str
    contract: dict[str, Any] = field(default_factory=dict)


def _get_backend():
    """Get the active search backend (lazy, with circular-import guard)."""
    from almanac.search_backend import get_backend

    return get_backend()


def _index_note(rel_path: str) -> None:
    """Re-index a note in the search backend (best-effort)."""
    try:
        from almanac.search_backend import get_backend as _get_b

        backend = _get_b()
        if hasattr(backend, "index_note"):
            backend.index_note(rel_path)
    except Exception:
        logger.debug("Could not re-index %s", rel_path, exc_info=True)


def _update_project_index(vault: Path, project_slug: str | None, note_stem: str, summary: str) -> None:
    """Update the project index file (best-effort)."""
    if not project_slug:
        return
    try:
        from almanac.store import update_project_index

        update_project_index(vault, project_slug, note_stem, summary)
    except Exception:
        logger.debug("Could not update project index for %s", note_stem, exc_info=True)


def _is_embedding_backend(backend) -> bool:
    """Check whether *backend* is a vector-capable embedded search backend."""
    name = type(backend).__name__
    if name == "EmbeddedSearchBackend":
        return getattr(backend, "_vec_available", False)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compatible_claim(fields, existing_body: str, incoming_body: str, note_type: str | None = None) -> bool:
    """Conservative local guard; uncertain intent stays on the review path."""
    if note_type and (fields.get("type") or "discovery") != note_type:
        return False
    negative = r"\b(no longer|never|avoid|do not|don.t|must not|cannot|forbid|disable|disallow)\b"
    if bool(re.search(negative, existing_body, re.IGNORECASE)) != bool(
        re.search(negative, incoming_body, re.IGNORECASE)
    ):
        return False
    replacement = r"\b(supersede[sd]?|replace[sd]?|instead|switch to|no longer)\b"
    return re.search(replacement, incoming_body, re.IGNORECASE) is None


def find_merge_target(
    title: str,
    body: str,
    *,
    tags: list[str] | None = None,
    project: str | None = None,
    note_type: str | None = None,
    threshold: float | None = None,
) -> MergeTarget | None:
    """Search the vault for a near-duplicate note using embedding similarity.

    Returns a ``MergeTarget`` when the best match's vector-similarity score
    is at or above *threshold*.  Returns ``None`` when:
    - no vector-capable backend is available
    - every candidate scores below the threshold
    - the backend search fails

    Callers should fall through to existing token-overlap logic when this
    returns ``None``.
    """
    backend = _get_backend()
    if not _is_embedding_backend(backend):
        return None

    if threshold is None:
        config = get_config()
        threshold = float(config.get("dedup_embed_threshold", 0.86))

    query = f"{title}\n{body[:2000]}"

    try:
        results = backend.search(
            query,
            collection="almanac",
            limit=5,
            semantic=True,
            timeout=10,
            min_score=threshold,
            concrete=False,
        )
    except Exception:
        logger.debug("Embedding search in dedup_merge failed", exc_info=True)
        return None

    if not results:
        return None

    vault = get_vault()
    config = get_config()
    min_title_overlap = float(config.get("dedup_embed_min_title_overlap", 0))
    for best in results[:5]:
        score = float(best.get("score", 0.0))
        if score < threshold:
            continue
        candidate_path = str(best.get("path", ""))
        loaded = _load_canonical(vault, candidate_path)
        if loaded is None:
            continue
        _, raw_text = loaded
        fields, existing_body = frontmatter.parse(raw_text)
        if not compatible_claim(fields, existing_body, body, note_type):
            continue
        if not note_eligible(fields, purpose="merge", project=project):
            continue
        candidate_title = str(fields.get("title") or "")
        if min_title_overlap > 0:
            cand_tokens = set(re.findall(r"[a-z0-9]+", candidate_title.lower()))
            inc_tokens = set(re.findall(r"[a-z0-9]+", title.lower()))
            overlap = len(cand_tokens & inc_tokens) / max(len(inc_tokens), 1)
            if overlap < min_title_overlap:
                continue
        return MergeTarget(
            path=candidate_path,
            similarity=score,
            title=candidate_title,
            contract={**fields, "note_type": fields.get("type") or "discovery"},
        )
    return None


def _load_canonical(vault: Path, path: str) -> tuple[Path, str] | None:
    """Read only existing Markdown notes contained by this vault."""
    try:
        root = Path(vault).resolve()
        target = (root / path).resolve()
        rel = target.relative_to(root)
        if not rel.parts or rel.parts[0] != "notes" or target.suffix != ".md":
            return None
        raw = target.read_text(encoding="utf-8")
        fm, _ = frontmatter.split_frontmatter(raw)
        if not fm:
            return None
        return target, raw
    except (OSError, ValueError, UnicodeError):
        return None


def merge_into_canonical(vault: Path, canonical_path: str, title: str, body: str, **kwargs) -> dict[str, Any]:
    """Append under the vault write lock; preserve the original claim's metadata.

    Incoming provenance belongs to the appended section. Explicit changes to
    established certainty, validity or origin require a deliberate replacement.
    """
    already_held = owns_vault_write_lock()
    if not already_held and not acquire_vault_write_lock():
        return {"canonical_path": canonical_path, "merged": False, "reason": "lock_unavailable"}
    try:
        return _merge_into_canonical(vault, canonical_path, title, body, **kwargs)
    finally:
        if not already_held:
            release_vault_write_lock()


def _merge_into_canonical(
    vault: Path,
    canonical_path: str,
    title: str,
    body: str,
    *,
    note_type: str = "discovery",
    tags: list[str] | None = None,
    certainty: int | None = None,
    source: str = "mcp",
    origin: str | None = None,
    validity_context: str | None = None,
    supersedes: str | None = None,
    project: str | None = None,
    branch: str | None = None,
    session_id: str | None = None,
    citations: list[dict] | None = None,
    expected_revision: str | None = None,
    evidence: dict | None = None,
) -> dict[str, Any]:
    """Locked implementation; only tags are changed on the canonical claim."""
    result = {"canonical_path": canonical_path, "merged": False}
    loaded = _load_canonical(vault, canonical_path)
    if loaded is None:
        return {**result, "reason": "canonical_missing_or_malformed"}
    canonical_abs, raw_text = loaded
    from almanac.revisions import require_revision, RevisionConflict

    try:
        require_revision(raw_text, expected_revision)
    except RevisionConflict as exc:
        return {**result, **exc.details}
    frontmatter_raw, canonical_body = frontmatter.split_frontmatter(raw_text)
    fields, _ = frontmatter.parse(raw_text)
    if not note_eligible(fields, purpose="merge", project=project):
        return {**result, "reason": "ineligible_canonical"}
    if supersedes:
        return {**result, "reason": "supersession_requires_review"}
    if not compatible_claim(fields, canonical_body, body, note_type):
        return {**result, "reason": "claim_intent_requires_review"}
    # Render incoming provenance with the shared sanitizer, but keep it scoped
    # to this section rather than asserting it for the original claim.
    incoming_fm, _ = frontmatter.split_frontmatter(
        _render_note_markdown(
            title,
            body,
            note_type,
            tags or [],
            certainty=certainty,
            source=source,
            origin=origin,
            validity_context=validity_context,
            supersedes=supersedes,
            project=project,
            branch=branch,
            session_id=session_id,
            citations=citations,
            evidence=evidence,
        )
    )
    safe_title = frontmatter.get_scalar(incoming_fm, "title") or "Incoming note"
    # Retry identity includes evidence/provenance, not just claim text. A new
    # citation for the same text must survive; routine write dates are excluded.
    stable_fm = re.sub(r"^date:.*$", "", incoming_fm, flags=re.MULTILINE)
    merge_id = hashlib.sha256(f"{stable_fm}\n{body.strip()}".encode()).hexdigest()
    marker = f"<!-- almanac-merge:v1:{merge_id} -->"
    if marker in canonical_body:
        return {**result, "reason": "already_merged"}
    # Compatibility with merges written before scoped provenance existed.
    if "almanac-merge:v1:" not in canonical_body and not citations and _already_merged(canonical_body, title, body):
        return {**result, "reason": "already_merged"}
    merged_body = canonical_body.rstrip() + "\n\n---\n\n"
    merged_body += f"{_MERGED_SECTION_HEADER} {safe_title}\n\n{marker}\n\n{body}\n\n"
    merged_body += f"Incoming provenance (this section only):\n\n```yaml\n{incoming_fm}\n```\n"

    incoming = normalize_note_contract(note_type=note_type, tags=tags or [])
    merged_tags = sorted(set(frontmatter.get_list(frontmatter_raw, "tags") + incoming["tags"]))
    # Keep the original bytes of every other field, including comments and
    # blank lines inside unknown multiline values. Only tags are managed here.
    merged_fm = re.sub(r"^tags:[^\n]*(?:\n[ \t]+[^\n]*)*", "", frontmatter_raw, flags=re.MULTILINE)
    merged_fm += f"\ntags: {json.dumps(merged_tags, ensure_ascii=False)}"
    try:
        _write_text_atomic(canonical_abs, f"---\n{merged_fm}\n---\n{merged_body}")
    except OSError as exc:
        return {**result, "reason": f"write_error: {exc}"}
    canonical_title = str(fields.get("title") or canonical_abs.stem)
    canonical_project = fields.get("project")

    # --- Re-index the canonical note ---
    _index_note(canonical_path)

    # --- Update project index ---
    if project or canonical_project:
        slug_val = project or canonical_project or ""
        project_slug = slugify(Path(slug_val).name)
        if project_slug:
            _update_project_index(
                vault,
                project_slug,
                canonical_abs.stem,
                f"Merged: {title[:80]}",
            )

    # --- Re-key access log (if paths changed) ---
    _maybe_rekey_access_log(canonical_path, canonical_path)

    return {
        "canonical_path": canonical_path,
        "merged": True,
        "reason": "ok",
        "canonical_title": canonical_title,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _already_merged(canonical_body: str, incoming_title: str, incoming_body: str) -> bool:
    """Return True if *incoming_body* already appears under a merged section."""
    # Fast path: check for the exact header string + title
    header = f"{_MERGED_SECTION_HEADER} {incoming_title}"
    if header not in canonical_body:
        return False

    # For a more robust check, see if the incoming body text is present
    # anywhere in the canonical body after any merged section.
    stripped = incoming_body.strip()
    if not stripped:
        return False

    # Check if the incoming body appears verbatim after the header
    sections = canonical_body.split(header)
    if len(sections) > 1:
        # The section after the header contains this merge's text
        if stripped in sections[1]:
            return True

    return False


def _maybe_rekey_access_log(old_path: str, canonical_path: str) -> None:
    """Re-key access-log stats from *old_path* to *canonical_path* if they differ.

    In the primary use case (preventing a new note from being created), the
    old and canonical paths are the same so this is a no-op.  When an actual
    supersede has happened (a note existed and was replaced by another stem),
    this moves those access-log events so the canonical retains the signal.
    """
    if old_path == canonical_path:
        return

    try:
        stats = load_access_log_stats()
    except Exception:
        logger.debug("Could not load access log stats for re-key", exc_info=True)
        return

    if old_path not in stats:
        return

    old_events = stats.pop(old_path, {"events": []}).get("events", [])
    if not old_events:
        return

    canonical_events = stats.get(canonical_path, {"events": []})
    merged_events = canonical_events.get("events", []) + old_events
    stats[canonical_path] = {"events": merged_events}

    try:
        write_access_log_stats(stats)
    except Exception:
        logger.debug("Could not write re-keyed access log stats", exc_info=True)
