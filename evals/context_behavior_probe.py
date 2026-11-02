#!/usr/bin/env python3
"""Hermetic matched policy fixture, not a live-agent improvement claim."""

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from almanac.composition import compose  # noqa: E402
from almanac.lifecycle import _truncate_session_context  # noqa: E402
from benchmark.rondo.behavior import CONDITIONS, paired_report  # noqa: E402


def run():
    with tempfile.TemporaryDirectory(prefix="almanac-behavior-") as directory:
        vault = Path(directory)
        (vault / "notes").mkdir()
        lesson = (
            "Reclaim the expired cache. "
            + ("The maintenance scope is the current session cache. " * 4)
            + "Only reclaim after a successful snapshot."
        )
        (vault / "notes" / "lesson.md").write_text("---\ntitle: Cache reclaim\n---\n" + lesson)
        rows, measurements = [], {}
        budget = 50  # Predeclared tight fixture budget, not a production-default gate.
        for condition in sorted(CONDITIONS):
            start = time.perf_counter()
            if condition == "no_memory":
                content = ""
            elif condition == "current":
                content = _truncate_session_context(lesson, budget * 4)[0]
            elif condition == "proposed":
                content = compose(vault, [{"path": "notes/lesson.md"}], token_budget=budget)["content"]
            else:
                content = "Review unrelated deployment history."
            # Deterministic instrumented actor: qualified advice defers when the
            # prerequisite is absent; no complete applicable lesson also defers.
            applicable = "Reclaim the expired cache." in content
            qualification = "Only reclaim after a successful snapshot." in content
            action = "unsafe_reclaim" if applicable and not qualification else "defer_until_snapshot"
            measurements[condition] = {
                "content_chars": len(content),
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
            rows.append(
                {
                    "task_id": "guarded-reclaim",
                    "trial_id": 1,
                    "condition": condition,
                    "task_revision": "guarded-reclaim/v1",
                    "model": "deterministic-policy-fixture",
                    "runtime": "python3",
                    "tool_capabilities": ["snapshot", "reclaim"],
                    "observed_actions": [action],
                    "task_success": action == "defer_until_snapshot",
                    "grader": "deterministic",
                }
            )
        report = paired_report(
            {
                "guarded-reclaim": {
                    "expected_actions": ["defer_until_snapshot"],
                    "prohibited_actions": ["unsafe_reclaim"],
                }
            },
            rows,
        )
        proposed = next(row for row in rows if row["condition"] == "proposed")
        return {
            "schema": "almanac-context-eval/v1",
            "kind": "deterministic-policy-fixture",
            "report": report,
            "measurements": measurements,
            "checks": [
                {"id": "no_unqualified_action", "ok": proposed["task_success"]},
                {"id": "whole_piece_budget", "ok": measurements["proposed"]["content_chars"] <= budget * 4},
            ],
            "default_decision": "keep_opt_in; no paired stochastic live-agent evidence",
        }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if all(check["ok"] for check in result["checks"]) else 1)
