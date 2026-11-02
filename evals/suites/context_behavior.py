"""Deterministic context controls; live agent experiments remain explicit."""

from evals.common import CheckResult, PASS, FAIL
from evals.context_behavior_probe import run as probe


def run(context):
    result = probe()
    return [
        CheckResult(
            id=f"context_behavior.{check['id']}",
            suite="context_behavior",
            title=check["id"],
            status=PASS if check["ok"] else FAIL,
            details=[
                "Deterministic matched policy fixture; no live-agent causality claim. New defaults remain opt-in."
            ],
        )
        for check in result["checks"]
    ]
