"""Bounded source-repair and derived-review work on the existing sweeper cadence."""

import json
from pathlib import Path

from almanac.config import RUNTIME_DIR
from almanac.derivation import derived_review
from almanac.revisions import raw_revision, repair_sources
from almanac.store import acquire_vault_write_lock, owns_vault_write_lock, release_vault_write_lock, _write_text_atomic


def maintain_sources(vault: Path, backend, *, limit: int = 100, state_path: Path | None = None) -> dict:
    vault = Path(vault).resolve()
    path = state_path or Path(RUNTIME_DIR) / f"source-maintenance-{raw_revision(str(vault))[7:23]}.json"
    held = owns_vault_write_lock()
    if not held and not acquire_vault_write_lock():
        return {"error": "lock_unavailable"}
    try:
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            state = {}
        repair = repair_sources(vault, backend, state, limit=limit)
        review = derived_review(vault, limit=limit, cursor=state.get("derived_cursor", 0))
        state["derived_cursor"] = review["cursor"]
        existing = state.setdefault("derived_reviews", {})
        for reference in review["checked_paths"]:
            existing.pop(reference, None)
        existing.update({r["path"]: r for r in review["reviews"]})
        reverse = state.setdefault("reverse_dependencies", {})
        for source in list(reverse):
            reverse[source] = [ref for ref in reverse[source] if ref not in review["checked_paths"]]
            if not reverse[source]:
                del reverse[source]
        for source, dependents in review["reverse_dependencies"].items():
            reverse[source] = sorted(set(reverse.get(source, [])) | set(dependents))
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_atomic(path, json.dumps(state, sort_keys=True))
        return {"repair": repair, "review": review, "state_path": str(path)}
    finally:
        if not held:
            release_vault_write_lock()
