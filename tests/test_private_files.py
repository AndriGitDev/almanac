"""Permissions and failure boundaries for private vault persistence."""

import os
import stat
from concurrent.futures import ThreadPoolExecutor

import pytest

from almanac import private_files
from almanac.sync_ledger import spool_payload


def test_atomic_payload_is_private_under_permissive_umask(tmp_path):
    previous = os.umask(0)
    try:
        path = spool_payload(tmp_path, "capture", "synthetic", "private synthetic payload")
    finally:
        os.umask(previous)
    assert path.read_text() == "private synthetic payload"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_atomic_replace_does_not_follow_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("unchanged")
    target = tmp_path / "payload"
    target.symlink_to(outside)
    private_files.write_private_text(target, "new private payload")
    assert outside.read_text() == "unchanged"
    assert not target.is_symlink()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_failed_replace_preserves_original_and_removes_temporary(tmp_path, monkeypatch):
    target = tmp_path / "payload"
    target.write_text("previous")

    def fail(*args):
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr(private_files.os, "replace", fail)
    with pytest.raises(OSError):
        private_files.write_private_text(target, "replacement")
    assert target.read_text() == "previous"
    assert list(tmp_path.iterdir()) == [target]


def test_append_restricts_existing_file_before_new_content(tmp_path):
    target = tmp_path / "events.jsonl"
    target.write_text("first\n")
    target.chmod(0o644)
    private_files.append_private_text(target, "second\n")
    assert target.read_text() == "first\nsecond\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_append_refuses_symlink_and_fifo(tmp_path):
    target = tmp_path / "outside"
    target.write_text("unchanged")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        private_files.append_private_text(link, "private")
    assert target.read_text() == "unchanged"
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(OSError):
        private_files.append_private_text(fifo, "private")


def test_concurrent_appends_preserve_complete_records(tmp_path):
    target = tmp_path / "events.jsonl"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda n: private_files.append_private_text(target, f"record-{n}\n"), range(100)))
    assert sorted(target.read_text().splitlines()) == sorted(f"record-{n}" for n in range(100))
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
