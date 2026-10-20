"""Tests for vault identity generation and persistence."""

import json
from unittest.mock import patch

from almanac.config import get_vault_id


def _patch_identity(tmp_path):
    """Patch the per-vault identity path to a temporary location."""
    identity_path = tmp_path / "vault" / "vault-identity.json"
    return patch("almanac.config._vault_identity_path", return_value=identity_path), identity_path


class TestVaultIdentity:
    def test_generates_uuid(self, tmp_path):
        p1, identity_path = _patch_identity(tmp_path)
        with p1:
            vault_id = get_vault_id()
            assert vault_id
            assert len(vault_id) == 32  # hex UUID without dashes

    def test_persists_to_disk(self, tmp_path):
        p1, identity_path = _patch_identity(tmp_path)
        with p1:
            vault_id = get_vault_id()
            assert identity_path.exists()
            data = json.loads(identity_path.read_text())
            assert data["vault_id"] == vault_id
            assert "created" in data

    def test_returns_same_id_on_subsequent_calls(self, tmp_path):
        p1, identity_path = _patch_identity(tmp_path)
        with p1:
            id1 = get_vault_id()
            id2 = get_vault_id()
            assert id1 == id2

    def test_survives_corrupt_file(self, tmp_path):
        p1, identity_path = _patch_identity(tmp_path)
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text("not json{{{")
        with p1:
            vault_id = get_vault_id()
            assert vault_id
            assert len(vault_id) == 32

    def test_survives_missing_vault_id_key(self, tmp_path):
        p1, identity_path = _patch_identity(tmp_path)
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(json.dumps({"other": "data"}))
        with p1:
            vault_id = get_vault_id()
            assert vault_id
            assert len(vault_id) == 32

    def test_creates_parent_directories(self, tmp_path):
        p1, _ = _patch_identity(tmp_path)
        # Override to a deep nested path
        deep_path = tmp_path / "deep" / "nested" / "vault-identity.json"
        with patch("almanac.config._vault_identity_path", return_value=deep_path):
            get_vault_id()
            assert deep_path.exists()

    def test_two_vaults_get_different_ids(self, tmp_path):
        vault_a = tmp_path / "vault-a" / "vault-identity.json"
        vault_b = tmp_path / "vault-b" / "vault-identity.json"
        with patch("almanac.config._vault_identity_path", return_value=vault_a):
            id_a = get_vault_id()
        with patch("almanac.config._vault_identity_path", return_value=vault_b):
            id_b = get_vault_id()
        assert id_a != id_b
