import pytest

from benchmark.rondo.behavior import CONDITIONS, grade_behavior, paired_report


def test_reference_overlap_cannot_prove_lesson_application():
    grade = grade_behavior(
        {"expected_actions": ["retain_ttl_condition"], "prohibited_actions": ["unconditional_cache"]},
        {"memory_refs": ["notes/cache.md"], "task_success": True},
    )
    assert not grade["applied"]
    assert grade["missing_actions"] == ["retain_ttl_condition"]


def test_matched_report_requires_all_controls_and_pins():
    tasks = {"cache": {"expected_actions": ["retain_ttl_condition"]}}
    rows = [
        {
            "task_id": "cache",
            "trial_id": 1,
            "condition": condition,
            "task_revision": "rev1",
            "model": "deterministic-fixture",
            "runtime": "python3",
            "tool_capabilities": ["read"],
            "observed_actions": ["retain_ttl_condition"] if condition == "proposed" else [],
            "task_success": condition == "proposed",
        }
        for condition in CONDITIONS
    ]
    result = paired_report(tasks, rows)
    assert result["proposed_minus_current_success"] == 1
    assert result["approximate_95pct_halfwidth"] is None
    with pytest.raises(ValueError, match="all four"):
        paired_report(tasks, rows[:-1])
    rows[0]["task_revision"] = "different"
    with pytest.raises(ValueError, match="different pins"):
        paired_report(tasks, rows)


def test_real_composer_matched_policy_fixture():
    from evals.context_behavior_probe import run

    report = run()
    assert all(check["ok"] for check in report["checks"])
    assert report["default_decision"].startswith("keep_opt_in")
