"""Bounded retrieval -> pure composition -> optional host generation delivery."""

import os
import time
from pathlib import Path

from almanac.composition import compose, profile_definition
from almanac.config import detect_project, get_config, get_vault
from almanac.delivery import DeliveryLedger
from almanac.revisions import raw_revision

SITUATIONS = {"fresh", "resume", "post_compaction"}


def context_packet(
    *,
    cwd="",
    prompt="",
    session_id="unknown",
    token_budget=2000,
    profile=None,
    situation=None,
    host_id="cli",
    host_instance_id=None,
    context_epoch=None,
    preview=False,
    acknowledge_packet_id=None,
    delivery_outcome="attached",
    retry=False,
    candidates=None,
    config=None,
    vault=None,
    include_status=True,
    include_recent=True,
    include_recall=True,
    include_tool_context_preview=False,
) -> dict:
    started = time.perf_counter()
    config = get_config() if config is None else config
    vault = get_vault() if vault is None else Path(vault)
    if situation is not None and situation not in SITUATIONS:
        return {"error": "Unsupported context situation", "reason": "invalid_situation", "should_inject": False}
    if context_epoch is not None and (
        isinstance(context_epoch, bool) or not isinstance(context_epoch, int) or context_epoch < 0
    ):
        return {"error": "context_epoch must be a nonnegative integer", "should_inject": False}
    if situation == "post_compaction" and (context_epoch is None or not host_instance_id):
        return {
            "error": "Recovery requires host_instance_id and context_epoch",
            "reason": "missing_generation",
            "should_inject": False,
        }
    if host_id != "mcp" and candidates is None:
        from almanac.remote_client import is_remote, session_context as remote_context

        if is_remote():
            return remote_context(
                cwd=cwd,
                prompt=prompt,
                session_id=session_id,
                token_budget=token_budget,
                profile=profile or ("recovery" if situation == "post_compaction" else "orientation"),
                situation=situation,
                host_instance_id=host_instance_id,
                context_epoch=context_epoch,
                preview=preview,
                acknowledge_packet_id=acknowledge_packet_id,
                delivery_outcome=delivery_outcome,
                retry=retry,
                include_status=include_status,
                include_recent=include_recent,
                include_recall=include_recall,
                include_tool_context_preview=include_tool_context_preview,
            )
    project, _ = detect_project(cwd, None) if cwd else (None, None)
    scope = {
        "vault": str(vault.resolve()),
        "host": host_id,
        "instance": host_instance_id,
        "checkout": os.path.realpath(cwd) if cwd else "",
        "project": project,
        "session": session_id,
    }
    ledger = DeliveryLedger(scope) if host_instance_id and context_epoch is not None and not preview else None
    if ledger:
        generation = ledger.begin(context_epoch)
        if not generation["accepted"]:
            return {"should_inject": False, "content": "", "results": [], "metadata": {"delivery": generation}}
        if acknowledge_packet_id:
            return {
                "should_inject": False,
                "content": "",
                "results": [],
                "metadata": {
                    "delivery": ledger.acknowledge(context_epoch, acknowledge_packet_id, outcome=delivery_outcome)
                },
            }
    name = profile or ("recovery" if situation == "post_compaction" else "orientation")
    try:
        view = profile_definition(name, config=config, cwd=cwd)
        if candidates is None and not view["pieces"]:
            from almanac.search import qmd_search_with_extras

            query = (prompt if include_recall else "") or ((project or "") if include_recent else "")
            candidates = (
                qmd_search_with_extras(query, limit=20, semantic=False, timeout=5, min_score=0.0) if query else []
            )
        packet = compose(
            vault, candidates or [], token_budget=token_budget, profile=view, project=project, config=config
        )
    except (ValueError, OSError) as exc:
        return {
            "should_inject": False,
            "error": str(exc),
            "reason": "context_unavailable",
            "content": "",
            "results": [],
            "complete": False,
        }
    packet["packet_id"] = raw_revision(packet["packet_id"] + str(scope) + str(context_epoch))
    packet["source"] = "session-context"
    packet["sections"] = {"composition": {"profile": name, "selected_count": len(packet["pieces"])}}
    if include_status:
        packet["sections"]["status"] = {"vault_exists": vault.exists(), "context_schema": "almanac-context/v1"}
    if include_tool_context_preview:
        packet["sections"]["tool_context_preview"] = {"available": False, "reason": "file_path_required"}
    packet["metadata"].update(
        situation=situation or "fresh",
        context_epoch=context_epoch,
        preview=preview,
        adapter_capabilities={
            "version": 1,
            "host_event": "supplied" if situation else "unknown",
            "acknowledgment": "explicit-host-report" if ledger else "unsupported",
        },
    )
    if ledger and packet["should_inject"]:
        delivery = ledger.publish(context_epoch, packet["packet_id"], retry=retry)
        packet["metadata"]["delivery"] = delivery
        if not delivery["accepted"]:
            packet["should_inject"] = False
            packet["content"] = ""
            packet["pieces"] = []
            packet["results"] = []
            packet["metadata"].update(used_chars=0, estimated_tokens=0)
    packet["metadata"]["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return packet
