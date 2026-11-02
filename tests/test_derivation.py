import json

from almanac.derivation import derived_status, derived_review, source_snapshot


def test_source_name_set_does_not_hide_changed_or_missing_evidence(tmp_vault):
    source = tmp_vault / "notes" / "source.md"
    source.write_text("---\ntitle: Source\nresurfaced_count: 1\n---\nUse bounded TTL.")
    revisions = source_snapshot(tmp_vault, ["source"])
    pattern = (
        "---\ntitle: Pattern\nsource: inception\nsynthesized_from: [source]\nsynthesized_revisions: "
        + json.dumps(revisions)
        + "\n---\nA pattern."
    )
    (tmp_vault / "notes" / "pattern.md").write_text(pattern)
    assert derived_status(tmp_vault, pattern)["status"] == "current"
    source.write_text(source.read_text().replace("count: 1", "count: 20"))
    assert derived_status(tmp_vault, pattern)["status"] == "current"
    source.write_text(source.read_text().replace("bounded", "unbounded"))
    assert derived_status(tmp_vault, pattern)["sources"][0]["status"] == "changed"
    assert derived_review(tmp_vault)["reviews"][0]["path"] == "notes/pattern.md"
    source.unlink()
    assert derived_status(tmp_vault, pattern)["sources"][0]["status"] == "unavailable"


def test_archived_provenance_remains_resolvable(tmp_vault):
    source = tmp_vault / "notes" / "source.md"
    source.write_text("---\ntitle: Source\n---\nClaim.")
    revisions = source_snapshot(tmp_vault, ["source"])
    pattern = "---\nsynthesized_from: [source]\nsynthesized_revisions: " + json.dumps(revisions) + "\n---\nPattern."
    source.rename(tmp_vault / "archive" / "source.md")
    assert derived_status(tmp_vault, pattern)["sources"][0]["status"] == "archived"
    assert derived_status(tmp_vault, pattern)["status"] == "current"


def test_incremental_collection_revisits_processed_source_without_new_timestamp(tmp_vault):
    from memento_inception import collect_eligible_notes
    from almanac.revisions import semantic_revision

    path = tmp_vault / "notes" / "source.md"
    path.write_text("---\ntitle: Source\ndate: 2026-01-01\n---\nUse bounded TTL.")
    state = {
        "processed_notes": ["source"],
        "processed_revisions": {"source": semantic_revision(path.read_text())},
        "last_run_iso": "2026-11-01",
    }
    assert collect_eligible_notes({"vault_path": str(tmp_vault)}, state) == []
    path.write_text(path.read_text().replace("bounded", "unbounded"))
    assert [row.stem for row in collect_eligible_notes({"vault_path": str(tmp_vault)}, state)] == ["source"]


def test_known_source_change_excludes_derived_automatic_guidance(tmp_vault):
    from almanac.eligibility import filter_eligible_results
    from almanac.hub import _scan_notes

    source = tmp_vault / "notes" / "source.md"
    source.write_text("---\ntitle: Source\n---\nClaim A.")
    snapshot = source_snapshot(tmp_vault, ["source"])
    (tmp_vault / "notes" / "pattern.md").write_text(
        "---\ntitle: Pattern\nsynthesized_from: [source]\nsynthesized_revisions: "
        + json.dumps(snapshot)
        + "\n---\nDerived claim."
    )
    row = {"path": "notes/pattern.md"}
    assert filter_eligible_results(tmp_vault, [row])[0] == [row]
    source.write_text(source.read_text().replace("Claim A", "Claim B"))
    assert filter_eligible_results(tmp_vault, [row])[0] == []
    assert "pattern" not in _scan_notes(tmp_vault)
    assert filter_eligible_results(tmp_vault, [row], purpose="history")[0] == [row]


def test_periodic_review_clears_resolved_candidates(tmp_vault, tmp_path):
    from almanac.maintenance import maintain_sources

    class Backend:
        def index_note(self, path):
            return True

    source = tmp_vault / "notes" / "source.md"
    source.write_text("---\ntitle: Source\n---\nClaim.")
    pattern = tmp_vault / "notes" / "pattern.md"
    pattern.write_text("---\nsynthesized_from: [source]\n---\nPattern.")
    state_path = tmp_path / "maintenance.json"
    maintain_sources(tmp_vault, Backend(), state_path=state_path)
    assert json.loads(state_path.read_text())["derived_reviews"]
    snapshots = source_snapshot(tmp_vault, ["source"])
    pattern.write_text(
        "---\nsynthesized_from: [source]\nsynthesized_revisions: " + json.dumps(snapshots) + "\n---\nPattern."
    )
    maintain_sources(tmp_vault, Backend(), state_path=state_path)
    assert not json.loads(state_path.read_text())["derived_reviews"]
