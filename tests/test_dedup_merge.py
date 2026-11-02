"""Tests for capture-time dedup/merge via embedding."""

from __future__ import annotations

from pathlib import Path

import pytest

from almanac.dedup_merge import find_merge_target, merge_into_canonical
from almanac.store import write_note
from almanac.search_backend import SearchBackend


def _seed_note(vault: Path, *, title: str, body: str) -> str:
    result = write_note(
        vault,
        title=title,
        body=body,
        note_type="discovery",
        tags=["test"],
        certainty=3,
        source="test",
    )
    return str(result.relative_to(vault))


class _FakeBackend(SearchBackend):
    """A minimal SearchBackend that returns canned vector search results."""

    def __init__(self, results: list[dict] | None = None):
        self._results = results or []
        self._is_avail = True

    def is_available(self) -> bool:
        return self._is_avail

    def search(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        semantic: bool = False,
        timeout: int = 10,
        min_score: float = 0.0,
        concrete: bool = False,
    ) -> list[dict]:
        return [r for r in self._results if r.get("score", 0) >= min_score][:limit]

    def reindex(self, collection: str, embed: bool = True) -> bool:
        return True

    def index_note(self, rel_path: str) -> bool:
        return True

    def repair_index(self, collection: str) -> dict:
        return {"reindexed": False, "repaired": 0, "errors": []}

    def get(self, path: str, collection: str | None = None, timeout: int = 5) -> dict | None:
        """Not used by dedup tests; return None."""
        return None

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# find_merge_target
# ---------------------------------------------------------------------------


def test_find_merge_target_above_threshold_returns_match(tmp_vault, monkeypatch):
    """A close embedding match above the threshold returns a MergeTarget."""
    # Simulate a backend hit: a FakeBackend that returns a match
    path = _seed_note(tmp_vault, title="Redis cache guidance", body="Use TTL on Redis keys.")
    fake_backend = _FakeBackend(results=[{"path": path, "title": "Redis cache guidance", "score": 0.95}])
    monkeypatch.setattr("almanac.dedup_merge._is_embedding_backend", lambda _: True)
    monkeypatch.setattr("almanac.dedup_merge._get_backend", lambda: fake_backend)
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)

    target = find_merge_target(
        "Redis cache TTL policy",
        "Set explicit TTL on Redis keys to prevent stale reads.",
        tags=["redis", "caching"],
        threshold=0.5,
    )

    assert target is not None
    assert target.path == path
    assert target.similarity >= 0.9


def test_find_merge_target_returns_none_for_low_similarity(tmp_vault, monkeypatch):
    """Below-threshold embedding returns None (creates new note)."""
    _seed_note(tmp_vault, title="Redis cache guidance", body="Use TTL on Redis keys.")
    _seed_note(tmp_vault, title="Docker compose networking", body="Bridge network for inter-service comms.")

    fake_backend = _FakeBackend(
        results=[{"path": "notes/docker-compose-networking.md", "title": "Docker compose networking", "score": 0.3}]
    )
    monkeypatch.setattr("almanac.dedup_merge._is_embedding_backend", lambda _: True)
    monkeypatch.setattr("almanac.dedup_merge._get_backend", lambda: fake_backend)
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)

    target = find_merge_target(
        "PostgreSQL index tuning",
        "Use partial indexes for filtered queries.",
        tags=["postgres"],
        threshold=0.5,
    )
    assert target is None


def test_find_merge_target_fallback_when_provider_unavailable(tmp_vault, monkeypatch):
    """When the embedding provider is unavailable, fall back to token overlap (no merge)."""
    _seed_note(tmp_vault, title="Redis cache guidance", body="Use TTL on Redis keys.")

    # _is_embedding_backend returns False -> find_merge_target short-circuits to None
    monkeypatch.setattr("almanac.dedup_merge._is_embedding_backend", lambda _: False)
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)

    target = find_merge_target("Redis cache guidance", "Set explicit TTL on Redis keys.", threshold=0.86)
    assert target is None


# ---------------------------------------------------------------------------
# merge_into_canonical
# ---------------------------------------------------------------------------


def test_merge_appends_body_with_header(tmp_vault, monkeypatch):
    """merge_into_canonical appends incoming body under a Merged-from section."""
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)
    monkeypatch.setattr("almanac.dedup_merge.load_access_log_stats", lambda: {})
    monkeypatch.setattr("almanac.dedup_merge.write_access_log_stats", lambda _: None)
    monkeypatch.setattr("almanac.dedup_merge._update_project_index", lambda *a, **kw: None)
    monkeypatch.setattr("almanac.dedup_merge._index_note", lambda *a, **kw: None)

    path = _seed_note(tmp_vault, title="Redis cache guidance", body="Use TTL on Redis keys.")

    result = merge_into_canonical(
        tmp_vault,
        path,
        title="Redis TTL policy update",
        body="Set a 24-hour TTL for session caches.",
        note_type="discovery",
        tags=["redis", "ttl"],
        certainty=4,
    )

    assert result["canonical_path"] == path
    assert result["merged"] is True

    # Read the merged canonical note
    merged = (tmp_vault / path).read_text(encoding="utf-8")
    assert "Set a 24-hour TTL for session caches." in merged
    assert "## Merged from" in merged


def test_merge_unions_tags(tmp_vault, monkeypatch):
    """Merged note has the union of old and new tags."""
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)
    monkeypatch.setattr("almanac.dedup_merge.load_access_log_stats", lambda: {})
    monkeypatch.setattr("almanac.dedup_merge.write_access_log_stats", lambda _: None)
    monkeypatch.setattr("almanac.dedup_merge._update_project_index", lambda *a, **kw: None)
    monkeypatch.setattr("almanac.dedup_merge._index_note", lambda *a, **kw: None)

    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")
    merge_into_canonical(
        tmp_vault,
        path,
        title="Redis cache update",
        body="Additional guidance.",
        note_type="discovery",
        tags=["redis", "ttl"],
        certainty=3,
    )

    merged = (tmp_vault / path).read_text(encoding="utf-8")
    assert "redis" in merged
    assert "ttl" in merged


def test_merge_preserves_established_certainty(tmp_vault, monkeypatch):
    """Similarity and an incoming assertion do not establish stronger evidence."""
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)
    monkeypatch.setattr("almanac.dedup_merge.load_access_log_stats", lambda: {})
    monkeypatch.setattr("almanac.dedup_merge.write_access_log_stats", lambda _: None)
    monkeypatch.setattr("almanac.dedup_merge._update_project_index", lambda *a, **kw: None)
    monkeypatch.setattr("almanac.dedup_merge._index_note", lambda *a, **kw: None)

    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")  # certainty=3
    merge_into_canonical(
        tmp_vault,
        path,
        title="Redis cache update",
        body="More specific TTL guidance.",
        note_type="discovery",
        tags=["redis"],
        certainty=5,  # higher than existing 3
    )

    merged = (tmp_vault / path).read_text(encoding="utf-8")
    assert "certainty: 3" in merged


def test_merge_round_trips_metadata_and_scopes_incoming_evidence(tmp_vault, monkeypatch):
    monkeypatch.setattr("almanac.dedup_merge._index_note", lambda *a: None)
    monkeypatch.setattr("almanac.dedup_merge._update_project_index", lambda *a: None)
    path = _seed_note(tmp_vault, title="Redis cache", body="Original guidance.")
    note = tmp_vault / path
    original = note.read_text().replace("source: test", "source: human\norigin: original-decision")
    metadata = """pinned: true
synthesized_from:
  - source-a
last_resurfaced: 2026-11-01
validity-context: Only for session caches
project_path: /original/checkout
citations: [{"file": "old.py", "anchor": "original"}]
future-field: |
  keep this multiline value
  and this line
"""
    note.write_text(original.replace("---\n\n", metadata + "---\n\n", 1))
    result = merge_into_canonical(
        tmp_vault,
        path,
        "Redis cache detail",
        "Use a bounded TTL.",
        tags=["ttl"],
        source="capture",
        origin="new-session",
        certainty=5,
        citations=[{"file": "new.py", "anchor": "ttl"}],
    )
    assert result["merged"] is True
    from almanac.frontmatter import split_frontmatter

    fm, body = split_frontmatter(note.read_text())
    assert metadata.strip() in fm
    assert "source: human" in fm
    assert "origin: original-decision" in fm
    assert "new.py" not in fm
    assert '"new.py"' in body
    assert "origin: new-session" in body


@pytest.mark.parametrize(
    "extra,project",
    [
        ("invalidated_by: newer\n", None),
        ("project: other-project\n", "almanac"),
    ],
)
def test_merge_refuses_ineligible_note_without_changes(tmp_vault, extra, project):
    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")
    note = tmp_vault / path
    original = note.read_text().replace("---\n\n", extra + "---\n\n", 1)
    note.write_text(original)
    result = merge_into_canonical(tmp_vault, path, "Redis cache detail", "More detail.", project=project)
    assert result["merged"] is False
    assert note.read_text() == original


def test_find_merge_target_skips_ineligible_best_hits(tmp_vault, monkeypatch):
    paths = []
    for title, extra in [
        ("Invalid", "invalidated_by: newer\nproject: almanac\n"),
        ("Other", "project: other\n"),
        ("Eligible", "project: almanac\n"),
    ]:
        path = _seed_note(tmp_vault, title=title, body="Use TTL.")
        note = tmp_vault / path
        note.write_text(note.read_text().replace("---\n\n", extra + "---\n\n", 1))
        paths.append(path)
    backend = _FakeBackend([{"path": p, "score": 0.99 - i * 0.01} for i, p in enumerate(paths)])
    monkeypatch.setattr("almanac.dedup_merge._is_embedding_backend", lambda _: True)
    monkeypatch.setattr("almanac.dedup_merge._get_backend", lambda: backend)
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)
    target = find_merge_target("TTL", "Use a bounded TTL.", project="/code/almanac")
    assert target.path == paths[-1]


def test_failed_atomic_merge_preserves_original(tmp_vault, monkeypatch):
    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")
    original = (tmp_vault / path).read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("almanac.store.os.replace", fail)
    result = merge_into_canonical(tmp_vault, path, "Redis detail", "Bound the TTL.")
    assert result["merged"] is False
    assert (tmp_vault / path).read_bytes() == original
    assert not list((tmp_vault / "notes").glob(".tmp-*"))


def test_same_text_with_new_evidence_is_not_discarded_as_retry(tmp_vault, monkeypatch):
    monkeypatch.setattr("memento.dedup_merge._index_note", lambda *a: None)
    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")
    args = (tmp_vault, path, "Redis detail", "Bound the TTL.")
    assert merge_into_canonical(*args, citations=[{"file": "one.py", "anchor": "ttl"}])["merged"]
    assert merge_into_canonical(*args, citations=[{"file": "two.py", "anchor": "ttl"}])["merged"]
    assert not merge_into_canonical(*args, citations=[{"file": "two.py", "anchor": "ttl"}])["merged"]
    text = (tmp_vault / path).read_text()
    assert text.count("## Merged from") == 2
    assert "one.py" in text and "two.py" in text


def test_merge_idempotent_no_double_append(tmp_vault, monkeypatch):
    """Re-merging the same payload does not add a duplicate section."""
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)
    monkeypatch.setattr("almanac.dedup_merge.load_access_log_stats", lambda: {})
    monkeypatch.setattr("almanac.dedup_merge.write_access_log_stats", lambda _: None)
    monkeypatch.setattr("almanac.dedup_merge._update_project_index", lambda *a, **kw: None)
    monkeypatch.setattr("almanac.dedup_merge._index_note", lambda *a, **kw: None)

    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")

    subject = {
        "title": "Redis TTL update",
        "body": "Set 24h TTL for session caches.",
        "note_type": "discovery",
        "tags": ["redis"],
        "certainty": 3,
    }

    result1 = merge_into_canonical(tmp_vault, path, **subject)
    assert result1["merged"] is True

    # Second merge of same content
    result2 = merge_into_canonical(tmp_vault, path, **subject)
    # Should be idempotent
    assert result2["merged"] is False
    assert "already_merged" in result2.get("reason", "")

    # Verify only one extra section in the body
    merged = (tmp_vault / path).read_text(encoding="utf-8")
    count = merged.count("## Merged from")
    assert count == 1, f"Expected 1 merged section, got {count}"


def test_access_log_survives_merge(tmp_vault, monkeypatch):
    """After merge, the existing access-log stats for the canonical path survive."""
    monkeypatch.setattr("almanac.dedup_merge.get_vault", lambda: tmp_vault)
    monkeypatch.setattr("almanac.dedup_merge._update_project_index", lambda *a, **kw: None)
    monkeypatch.setattr("almanac.dedup_merge._index_note", lambda *a, **kw: None)

    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")

    # Pre-populate access log stats for the canonical
    initial_stats = {path: {"events": [{"ts": "2026-07-05T12:00:00", "rank": 1}]}}
    monkeypatch.setattr("almanac.dedup_merge.load_access_log_stats", lambda: initial_stats)

    merge_into_canonical(
        tmp_vault,
        path,
        title="Redis TTL update",
        body="Set 24h TTL.",
        note_type="discovery",
        tags=["redis"],
        certainty=3,
    )

    # The merge does not touch the access log when old == canonical path
    # (standard case).  Stats should still be in their pre-populated state.
    assert path in initial_stats
    assert len(initial_stats[path]["events"]) == 1


@pytest.mark.parametrize(
    "body,note_type", [("Do not use TTL; use leases instead.", "discovery"), ("Use bounded TTL.", "decision")]
)
def test_incompatible_claim_intent_requires_review(tmp_vault, body, note_type):
    path = _seed_note(tmp_vault, title="Redis cache", body="Use TTL.")
    original = (tmp_vault / path).read_bytes()
    result = merge_into_canonical(tmp_vault, path, "Redis cache", body, note_type=note_type)
    assert not result["merged"]
    assert result["reason"] == "claim_intent_requires_review"
    assert (tmp_vault / path).read_bytes() == original
