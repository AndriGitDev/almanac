import json
import zipfile

from almanac.archive import export_archive, export_preview
from almanac.composition import compose
from almanac.policy import effective_fields, inherited_policy, project_identity, reuse_decision
from almanac.revisions import semantic_revision

CONFIG = {"reuse_policy_enabled": True}


def test_restrictions_inherit_through_old_derived_notes(tmp_vault):
    restricted = tmp_vault / "notes" / "secret.md"
    restricted.write_text(
        "---\ntitle: Private\nproject: alpha\nreuse_scope: project\nexport_policy: deny\n---\nScoped implementation constraint."
    )
    pattern = tmp_vault / "notes" / "pattern.md"
    pattern.write_text(
        "---\ntitle: Pattern\nsynthesized_from: [secret]\nsynthesized_revisions: "
        + json.dumps({"secret": semantic_revision(restricted.read_text())})
        + "\n---\nDerived constraint."
    )
    fields = effective_fields(tmp_vault, {"synthesized_from": ["secret"]})
    assert fields["export_policy"] == "deny"
    assert not reuse_decision(fields, project="beta", config=CONFIG)["allowed"]
    assert reuse_decision(fields, project="alpha", config=CONFIG)["allowed"]
    assert not compose(tmp_vault, [{"path": "notes/pattern.md"}], project="beta", config=CONFIG)["content"]
    assert compose(tmp_vault, [{"path": "notes/pattern.md"}], project="alpha", config=CONFIG)["content"]
    preview = export_preview(tmp_vault, config=CONFIG, project="alpha")
    assert {row["path"] for row in preview["exclusions"]} == {"notes/secret.md", "notes/pattern.md"}
    archive = tmp_vault.parent / "out.zip"
    export_archive(tmp_vault, archive, config=CONFIG, project="alpha")
    with zipfile.ZipFile(archive) as package:
        assert not any(name.endswith("secret.md") or name.endswith("pattern.md") for name in package.namelist())


def test_aliases_and_incompatible_derived_projects():
    assert project_identity("/code/old", {"project_aliases": {"old": "new"}}) == "new"
    import pytest

    with pytest.raises(ValueError):
        project_identity("a", {"project_aliases": {"a": "b", "b": "a"}})
    with pytest.raises(ValueError):
        inherited_policy([{"project": "a", "reuse_scope": "project"}, {"project": "b", "reuse_scope": "project"}], {})
