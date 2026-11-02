"""Generation-safe packet return/acknowledgment bookkeeping, outside the vault."""

import fcntl
import json
import time
from pathlib import Path

from almanac.config import RUNTIME_DIR
from almanac.revisions import raw_revision


class DeliveryLedger:
    def __init__(self, scope: dict, *, directory: Path | None = None):
        self.scope = scope
        self.path = (directory or Path(RUNTIME_DIR)) / (
            "delivery-" + raw_revision(json.dumps(scope, sort_keys=True))[7:39] + ".json"
        )

    def _update(self, action):
        from almanac.store import _write_text_atomic

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Stable lock inode + atomic state rename survives interrupted publication.
            with self.path.with_suffix(".lock").open("a+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    state = json.loads(self.path.read_text())
                except FileNotFoundError:
                    state = {"schema": "almanac-delivery/v1", "epoch": -1}
                except ValueError:
                    return {"accepted": False, "reason": "delivery_state_corrupt"}
                if state.get("schema") != "almanac-delivery/v1" or not isinstance(state.get("epoch"), int):
                    return {"accepted": False, "reason": "delivery_schema_unsupported"}
                result = action(state)
                _write_text_atomic(self.path, json.dumps(state, sort_keys=True))
                return result
        except OSError:
            return {"accepted": False, "reason": "delivery_state_unavailable", "retryable": True}

    def begin(self, epoch: int) -> dict:
        def action(state):
            if epoch < state["epoch"]:
                return {"accepted": False, "reason": "stale_epoch"}
            if epoch > state["epoch"]:
                state.clear()
                state.update({"schema": "almanac-delivery/v1", "epoch": epoch, "stage": "prepared"})
            return {"accepted": True, "epoch": epoch, "stage": "prepared"}

        return self._update(action)

    def publish(self, epoch: int, packet_id: str, *, retry: bool = False) -> dict:
        def action(state):
            if epoch != state["epoch"]:
                return {"accepted": False, "reason": "stale_epoch"}
            if state.get("packet_id") == packet_id and state.get("stage") in {"returned", "attached"} and not retry:
                return {"accepted": False, "reason": "already_returned", "stage": state["stage"]}
            state.update(packet_id=packet_id, stage="returned", returned_at=time.time())
            return {"accepted": True, "stage": "returned", "acknowledged": False}

        return self._update(action)

    def acknowledge(self, epoch: int, packet_id: str, *, outcome: str = "attached") -> dict:
        if outcome not in {"attached", "failed"}:
            return {"accepted": False, "reason": "unsupported_acknowledgment"}

        def action(state):
            if epoch != state["epoch"] or packet_id != state.get("packet_id"):
                return {"accepted": False, "reason": "stale_acknowledgment"}
            state.update(stage=outcome)
            return {"accepted": True, "stage": outcome, "meaning": "host report, not model usage"}

        return self._update(action)
