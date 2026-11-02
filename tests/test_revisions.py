import os

import pytest

from almanac.revisions import (
    RevisionConflict,
    raw_revision,
    semantic_revision,
    repair_sources,
    stamp_results,
    results_fresh,
)
from almanac.store import replace_note_at_path


def note(vault):
    path = vault / "notes" / "n.md"
    path.write_text("---\ntitle: N\nresurfaced_count: 1\nlast_resurfaced: 2026-01-01\n---\nOnly with a bounded TTL.\n")
    return path


def test_conditional_replace_serializes_writers(tmp_vault):
    path = note(tmp_vault)
    revision = raw_revision(path.read_bytes())
    args = (tmp_vault, "notes/n.md", "N", "Changed claim.", "discovery", [])
    replace_note_at_path(*args, expected_revision=revision)
    changed = path.read_bytes()
    with pytest.raises(RevisionConflict):
        replace_note_at_path(*args, expected_revision=revision)
    assert path.read_bytes() == changed


def test_semantic_revision_ignores_only_telemetry(tmp_vault):
    path = note(tmp_vault)
    original = path.read_text()
    assert semantic_revision(original) == semantic_revision(
        original.replace("count: 1", "count: 200").replace("2026-01-01", "2026-11-02")
    )
    assert semantic_revision(original) != semantic_revision(original.replace("bounded", "unbounded"))
    assert semantic_revision(original) != semantic_revision(
        original.replace("title: N", "title: N\ninvalidated_by: newer")
    )


def test_cache_and_repair_detect_preserved_mtime_edits(tmp_vault):
    path = note(tmp_vault)
    rows = stamp_results(tmp_vault, [{"path": "notes/n.md"}])
    assert results_fresh(tmp_vault, rows)

    class Backend:
        def index_note(self, path):
            return True

    state = {}
    assert repair_sources(tmp_vault, Backend(), state)["repaired"] == 1
    before = path.stat()
    path.write_text(path.read_text().replace("bounded", "unbounded"))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert not results_fresh(tmp_vault, rows)
    assert repair_sources(tmp_vault, Backend(), state)["repaired"] == 1


def test_explicit_metadata_omission_and_removal_are_distinct(tmp_vault):
    path = note(tmp_vault)
    path.write_text(
        path.read_text().replace("title: N", 'title: N\nevidence: {"method":"observation","summary":"Observed once"}')
    )
    args = (tmp_vault, "notes/n.md", "N", "Changed.", "discovery", [])
    replace_note_at_path(*args, expected_revision=raw_revision(path.read_bytes()))
    assert "Observed once" in path.read_text()
    replace_note_at_path(*args, expected_revision=raw_revision(path.read_bytes()), metadata_updates={"evidence": None})
    assert "evidence:" not in path.read_text()


def test_old_server_cannot_silently_accept_conditional_writes(monkeypatch):
    from almanac import remote_client

    calls = []
    monkeypatch.setattr(remote_client, "_call_tool", lambda name, args, **kw: calls.append(name) or {})
    result = remote_client.replace_note("notes/n.md", "N", "Claim.", expected_revision="sha256:old")
    assert result["reason"] == "conditional_writes_unsupported"
    assert calls == ["almanac_status"]


def test_same_process_threads_do_not_share_reentrant_lock_ownership(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from almanac.store import acquire_vault_write_lock, owns_vault_write_lock, release_vault_write_lock

    lock = tmp_path / "lock"
    assert acquire_vault_write_lock(lock_file=lock)
    try:
        with ThreadPoolExecutor(1) as pool:
            assert pool.submit(owns_vault_write_lock, lock).result() is False
        assert owns_vault_write_lock(lock)
    finally:
        release_vault_write_lock(lock_file=lock)


def test_concurrent_conditional_writers_have_one_winner(tmp_vault):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    path = note(tmp_vault)
    revision = raw_revision(path.read_bytes())
    barrier = threading.Barrier(2)

    def write(body):
        barrier.wait()
        try:
            replace_note_at_path(tmp_vault, "notes/n.md", "N", body, "discovery", [], expected_revision=revision)
            return "written"
        except RevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(write, body) for body in ["Claim A.", "Claim B."]]
        assert sorted(f.result() for f in futures) == ["conflict", "written"]
