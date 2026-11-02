import pytest

from almanac.composition import compose, profile_definition
from almanac.context import context_packet
from almanac.delivery import DeliveryLedger


@pytest.fixture
def sources(tmp_vault):
    for stem, text in [
        ("action", "Only use leases if the ownership caveat below applies."),
        ("caveat", "The holder must retain exclusive ownership throughout the operation."),
    ]:
        (tmp_vault / "notes" / f"{stem}.md").write_text(f"---\ntitle: {stem}\n---\n# Guidance\n{text}")
    return tmp_vault


def view():
    return {
        "name": "test",
        "version": 1,
        "pieces": [
            {"reference": "action#guidance", "priority": 100, "required": True, "requires": ["caveat#guidance"]},
            {"reference": "caveat#guidance", "priority": 50},
        ],
    }


def test_complete_dependency_group_or_honest_omission(sources):
    packet = compose(sources, [], token_budget=2000, profile=view())
    assert packet["complete"] and "exclusive ownership throughout" in packet["content"]
    assert len(packet["pieces"]) == 2
    for piece in packet["pieces"]:
        assert packet["content"][piece["start"] : piece["end"]]
    tiny = compose(sources, [], token_budget=1, profile=view())
    assert not tiny["complete"] and not tiny["content"]
    assert tiny["metadata"]["omissions"][0]["reason"] == "dependency-group-exceeds-budget"


def test_cycles_and_missing_prerequisites_fail_before_source_reads():
    bad = {
        "context_profiles": {
            "cycle": {"pieces": [{"reference": "a", "requires": ["b"]}, {"reference": "b", "requires": ["a"]}]}
        }
    }
    with pytest.raises(ValueError, match="cycle"):
        profile_definition("cycle", config=bad)


def test_preview_matches_delivery_source_snapshot_without_writes(sources, tmp_path, monkeypatch):
    import almanac.delivery as delivery

    monkeypatch.setattr(delivery, "RUNTIME_DIR", str(tmp_path / "runtime"))
    config = {"context_profiles": {"test": {"pieces": view()["pieces"]}}}
    args = dict(
        vault=sources, config=config, profile="test", cwd="", session_id="s", host_instance_id="client", context_epoch=1
    )
    before = {p: p.read_bytes() for p in sources.rglob("*.md")}
    preview = context_packet(**args, preview=True)
    assert not (tmp_path / "runtime").exists()
    packet = context_packet(**args)
    assert preview["content"] == packet["content"]
    assert preview["packet_id"] == packet["packet_id"]
    assert not context_packet(**args)["should_inject"]
    assert before == {p: p.read_bytes() for p in sources.rglob("*.md")}
    args["context_epoch"] = 2
    assert context_packet(**args, situation="post_compaction")["should_inject"]


def test_old_request_and_ack_cannot_overwrite_new_generation(tmp_path):
    ledger = DeliveryLedger({"client": "a"}, directory=tmp_path)
    ledger.begin(1)
    ledger.begin(2)
    assert not ledger.publish(1, "old")["accepted"]
    assert ledger.publish(2, "new")["accepted"]
    assert not ledger.acknowledge(1, "old")["accepted"]
    restarted = DeliveryLedger({"client": "a"}, directory=tmp_path)
    assert not restarted.publish(2, "new")["accepted"]
    assert restarted.acknowledge(2, "new", outcome="failed")["accepted"]
    assert restarted.publish(2, "new")["accepted"]
    other = DeliveryLedger({"client": "b"}, directory=tmp_path)
    assert other.begin(0)["accepted"]
    assert other.publish(0, "new")["accepted"]
