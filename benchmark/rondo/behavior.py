"""Observable-action grading and matched-condition reports; no inference from refs."""

import math
from collections import defaultdict

CONDITIONS = {"no_memory", "current", "proposed", "irrelevant_or_stale"}
PIN_FIELDS = ("task_revision", "model", "runtime", "tool_capabilities")


def grade_behavior(task: dict, outcome: dict) -> dict:
    expected = set(task.get("expected_actions", []))
    prohibited = set(task.get("prohibited_actions", []))
    observed = set(outcome.get("observed_actions", []))
    missing = sorted(expected - observed)
    violations = sorted(observed & prohibited)
    supported = bool(expected) and outcome.get("grader", "deterministic") == "deterministic"
    return {
        "grader": outcome.get("grader", "deterministic"),
        "supported": supported,
        "applied": supported and not missing and not violations,
        "missing_actions": missing,
        "constraint_violations": violations,
        "task_success": outcome.get("task_success") is True,
        "causal_improvement": "requires_matched_trials",
    }


def paired_report(tasks: dict, outcomes: list[dict]) -> dict:
    groups = defaultdict(dict)
    for row in outcomes:
        condition = row.get("condition")
        if condition not in CONDITIONS:
            raise ValueError("Unsupported matched condition")
        key = (row["task_id"], row["trial_id"])
        if condition in groups[key]:
            raise ValueError("Repeated condition in trial")
        if any(field not in row for field in PIN_FIELDS):
            raise ValueError("Matched runs require pinned task/model/runtime/tool settings")
        groups[key][condition] = row
    differences, failures = [], []
    for (task_id, trial_id), group in groups.items():
        if set(group) != CONDITIONS:
            raise ValueError("Every trial requires all four matched conditions")
        rows = list(group.values())
        if any(any(row[field] != rows[0][field] for field in PIN_FIELDS) for row in rows[1:]):
            raise ValueError("Matched conditions have different pins")
        grades = {condition: grade_behavior(tasks[task_id], row) for condition, row in group.items()}
        difference = int(grades["proposed"]["task_success"]) - int(grades["current"]["task_success"])
        differences.append(difference)
        for condition, grade in grades.items():
            if not grade["applied"] or not grade["task_success"]:
                failures.append({"task_id": task_id, "trial_id": trial_id, "condition": condition, "grade": grade})
    count = len(differences)
    mean = sum(differences) / count if count else None
    # Descriptive paired interval; small samples/stochastic execution remain explicit.
    uncertainty = None
    if count > 1:
        variance = sum((d - mean) ** 2 for d in differences) / (count - 1)
        uncertainty = 1.96 * math.sqrt(variance / count)
    return {
        "schema": "almanac-behavior-report/v1",
        "paired_trials": count,
        "proposed_minus_current_success": mean,
        "approximate_95pct_halfwidth": uncertainty,
        "uncertainty_note": "Descriptive normal interval; repeat stochastic live-agent trials and inspect failure examples",
        "failure_examples": failures[:30],
        "causal_improvement": "not_established_by_retrieval_overlap",
    }
