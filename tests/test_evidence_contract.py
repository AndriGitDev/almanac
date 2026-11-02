from almanac.evidence import read_evidence
from almanac.frontmatter import split_frontmatter
from almanac.store import write_note
from almanac.retrieval_policy import citation_evidence


def test_capture_and_merge_keep_applicability_without_invented_support(tmp_vault):
    from almanac.dedup_merge import merge_into_canonical

    evidence = {
        "method": "code_check",
        "summary": "TTL assertion passed.",
        "applicability": "Only session caches.",
        "action": "Set TTL.",
        "invalidating_conditions": "Different cache ownership.",
    }
    path = write_note(tmp_vault, "Cache", "Use bounded TTL.", "discovery", [], evidence=evidence)
    fm, _ = split_frontmatter(path.read_text())
    assert read_evidence(fm) == evidence
    merge_into_canonical(
        tmp_vault, str(path.relative_to(tmp_vault)), "Cache detail", "Additional condition.", evidence=evidence
    )
    fm, body = split_frontmatter(path.read_text())
    assert read_evidence(fm) == evidence
    assert "Only session caches." in body


def test_mixed_evidence_is_partial_and_missing_repo_is_not_stale(tmp_vault, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ok.py").write_text("bounded_ttl = 60")
    note = tmp_vault / "notes" / "n.md"
    note.write_text(
        "---\nproject_path: "
        + str(repo)
        + '\ncitations: [{"file":"ok.py","anchor":"bounded_ttl"},{"file":"missing.py","anchor":"absent"}]\n---\nClaim.'
    )
    result = citation_evidence(tmp_vault, {"path": "notes/n.md"})
    assert result["status"] == "partial"
    assert "semantic proof" in result["meaning"]
    (repo / "ok.py").unlink()
    assert citation_evidence(tmp_vault, {"path": "notes/n.md"})["status"] == "unverifiable"


def test_composer_keeps_frontmatter_qualification_with_the_advice(tmp_vault):
    from almanac.composition import compose

    path = write_note(
        tmp_vault,
        "Lease",
        "Use leases.",
        "decision",
        [],
        validity_context="Only under exclusive ownership.",
        evidence={
            "method": "human_decision",
            "applicability": "Session caches only.",
            "summary": "Avoid cross-owner writes.",
        },
    )
    packet = compose(tmp_vault, [{"path": str(path.relative_to(tmp_vault))}], token_budget=1000)
    assert "Only under exclusive ownership." in packet["content"]
    assert "Session caches only." in packet["content"]
    assert "not claim verification" in packet["content"]
    tiny = compose(tmp_vault, [{"path": str(path.relative_to(tmp_vault))}], token_budget=2)
    assert not tiny["content"]
