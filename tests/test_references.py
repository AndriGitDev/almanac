import pytest

from almanac.references import SourceError, heading_slug, read_reference


def test_sections_include_children_preserve_metadata_and_reject_ambiguity(tmp_vault):
    path = tmp_vault / "notes" / "guide.md"
    path.write_text(
        "---\ntitle: Guide\ninvalidated_by: newer\n---\n# Scope\nOnly with TTL.\n## Why\nBecause stale data matters.\n# Other\nNo.\n"
    )
    result = read_reference(tmp_vault, "guide#scope")
    assert "Because stale" in result["content"] and "# Other" not in result["content"]
    assert result["validity_status"] == "invalidated"
    assert result["revision"].startswith("sha256:")
    path.write_text("# Árvík\nFirst\n# Ａ́rvík\nSecond")
    assert heading_slug("Árvík") == heading_slug("Ａ́rvík")
    with pytest.raises(SourceError, match="Repeated"):
        read_reference(tmp_vault, "guide#árvík")


def test_fenced_and_comment_headings_are_ignored(tmp_vault):
    path = tmp_vault / "notes" / "n.md"
    path.write_text("<!--\n# Hidden\n-->\n```md\n# Hidden\n```\n# Visible\nKeep this whole caveat.\n")
    assert "whole caveat" in read_reference(tmp_vault, "n#visible")["content"]
    with pytest.raises(SourceError) as error:
        read_reference(tmp_vault, "n#hidden")
    assert error.value.reason == "missing_section"
    path.write_text("# Visible\n```\n")
    with pytest.raises(SourceError) as error:
        read_reference(tmp_vault, "n#visible")
    assert error.value.reason == "malformed_markdown"


def test_symlink_and_traversal_denied_before_read(tmp_vault, tmp_path):
    secret = tmp_path / "outside.md"
    secret.write_text("outside")
    (tmp_vault / "notes" / "escape.md").symlink_to(secret)
    for ref in ["notes/escape.md", "../outside.md"]:
        with pytest.raises(SourceError) as error:
            read_reference(tmp_vault, ref)
        assert error.value.reason == "denied_source"


def test_html_comment_literal_in_code_does_not_hide_closing_fence(tmp_vault):
    path = tmp_vault / "notes" / "code.md"
    path.write_text("```html\n<!-- not a Markdown comment\n```\n# Scope\nOnly with TTL.\n")
    assert "Only with TTL." in read_reference(tmp_vault, "code#scope")["content"]
