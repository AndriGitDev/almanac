"""One invalidated-note fixture across derivation and delivery boundaries."""

import json
import importlib.util
import sys
import time
from pathlib import Path

import pytest

from almanac import graph, hub, lifecycle
from almanac.eligibility import filter_eligible_results, note_eligible
from almanac.query import read_note_record
from almanac.retrieval_policy import PromptRecallRequest, PromptRecallRuntime


@pytest.fixture
def invalidated_note(tmp_vault, monkeypatch):
    for name in ("old", "current"):
        invalidation = "invalidated_by: current\n" if name == "old" else ""
        (tmp_vault / "notes" / f"{name}.md").write_text(
            f"---\ntitle: {name}\ntype: decision\nproject: almanac\ncertainty: 4\n"
            f"source: manual\ndate: 2026-11-01\n{invalidation}---\nUse bounded TTL.\n"
        )
    monkeypatch.setattr(lifecycle, "get_vault", lambda: tmp_vault)
    monkeypatch.setattr(graph, "get_vault", lambda: tmp_vault)
    monkeypatch.setattr(hub, "load_or_build_graph", lambda *a: (None, None))
    return tmp_vault, {"path": "notes/old.md", "title": "old", "score": 0.99, "snippet": "Use bounded TTL."}


def test_shared_policy_allows_explicit_history(invalidated_note):
    vault, row = invalidated_note
    record = read_note_record(vault, row["path"])
    for purpose in ("context", "synthesis", "merge"):
        assert not note_eligible(record, purpose=purpose, project="almanac")
    assert note_eligible(record, purpose="history")
    assert filter_eligible_results(vault, [row], purpose="history") == ([row], 0)
    assert record["invalidated_by"] == "current"
    assert lifecycle.read_note_oneliner("old") is None


@pytest.mark.parametrize("hook", ["almanac-inception.py"])
def test_hubs_maps_and_inception_exclude_same_invalidated_note(invalidated_note, hook):
    hook_path = Path(__file__).resolve().parents[1] / "hooks" / hook
    spec = importlib.util.spec_from_file_location("eligibility_inception", hook_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    build_project_maps, collect_eligible_notes = module.build_project_maps, module.collect_eligible_notes

    vault, _ = invalidated_note
    assert set(hub._scan_notes(vault)) == {"current"}
    hub.regenerate_project_hub(vault, "almanac")
    assert "[[old]]" not in (vault / "projects" / "almanac.md").read_text()
    assert "[[old]]" not in hub.vault_map(vault, "almanac")
    for full in (True, False):
        records = collect_eligible_notes({"vault_path": str(vault)}, {}, full=full)
        assert [record.stem for record in records] == ["current"]
    assert [row["stem"] for row in build_project_maps(vault)["almanac"]] == ["current"]
    # Previously generated maps must recheck current validity too.
    rows = graph.lookup_project_notes("almanac", maps={"almanac": [{"stem": "old", "certainty": 5}]})
    assert rows == []


@pytest.mark.parametrize("concrete", [True, False])
def test_automatic_recall_filters_even_literal_and_expanded_results(invalidated_note, concrete):
    vault, row = invalidated_note
    config = {
        "prompt_recall": True,
        "recall_concrete_mode": concrete,
        "recall_min_score": 0.4,
        "recall_max_notes": 3,
        "concept_index_enabled": False,
        "rrf_enabled": False,
        "prf_enabled": False,
        "multi_hop_enabled": False,
        "reranker_enabled": False,
    }
    runtime = PromptRecallRuntime(
        config_loader=lambda: config,
        vault_loader=lambda: vault,
        has_backend=lambda: True,
        remote_available=lambda: False,
        detect_project=lambda cwd: ("almanac", None),
        qmd_search=lambda *a, **kw: [dict(row)],
        enhance_results=lambda results, **kw: results + [dict(row)],
        recently_injected_paths=lambda *a, **kw: set(),
    )
    result = runtime.run(PromptRecallRequest(prompt="look up cache TTL", cwd="/code/almanac"))
    assert not result.should_inject
    assert result.reason == "invalidated-filtered-empty"


@pytest.mark.parametrize("cached", [True, False])
def test_tool_context_rechecks_current_note_before_injection(invalidated_note, monkeypatch, cached):
    vault, row = invalidated_note
    cwd, file_path = "/code/almanac", "/code/almanac/cache/runtime.py"
    cache = lifecycle._empty_tool_context_cache()
    if cached:
        key = lifecycle._tool_context_dir_key(cwd, file_path)
        cache["dirs"][key] = {"results": [row], "ts": time.time()}
    monkeypatch.setattr(lifecycle, "get_config", lambda: {"tool_context": True})
    monkeypatch.setattr(lifecycle, "has_qmd", lambda: True)
    monkeypatch.setattr(lifecycle, "load_cache", lambda: cache)
    monkeypatch.setattr(lifecycle, "save_cache", lambda c: None)
    monkeypatch.setattr(lifecycle, "enhance_results", lambda results, *a, **kw: results)
    monkeypatch.setattr(lifecycle, "extract_tool_context_keywords", lambda *a: "cache runtime")
    monkeypatch.setattr(lifecycle, "qmd_search_with_extras", lambda *a, **kw: [row])
    monkeypatch.setattr(lifecycle, "get_recall_paths", lambda *a, **kw: set())
    result = lifecycle.build_tool_context("Read", file_path, cwd, "session")
    assert not result.should_inject
    assert result.reason == "invalidated-filtered-empty"
    assert cache["injections"] == {}


def test_deferred_briefing_rechecks_after_preparation(invalidated_note, monkeypatch, tmp_path):
    _, row = invalidated_note
    monkeypatch.setattr(lifecycle, "DEFERRED_BRIEFING_PATH", str(tmp_path / "deferred.json"))
    cwd, session, project, host = "/code/almanac", "s1", "almanac", "pytest"
    path = Path(lifecycle.deferred_briefing_path(project, session, cwd, host))
    scope = lifecycle._deferred_scope(project, session, cwd, host)
    path.write_text(
        json.dumps(
            {
                "status": "ready",
                "timestamp": time.time(),
                "scope": scope,
                "note_lines": ["  - obsolete guidance"],
                "note_paths": [row["path"]],
            }
        )
    )
    assert lifecycle.consume_deferred_briefing(cwd, session, project, host) == []
    assert not path.exists()


def test_unavailable_metadata_fails_open_but_known_invalidation_does_not(tmp_vault):
    missing = {"path": "notes/unavailable.md"}
    invalidated_remote = {**missing, "invalidated_by": "newer"}
    assert filter_eligible_results(tmp_vault, [missing, invalidated_remote]) == ([missing], 1)
    assert filter_eligible_results(tmp_vault, [{**missing, "_meta": {"invalidated_by": "newer"}}]) == ([], 1)
