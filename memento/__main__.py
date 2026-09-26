"""Entry points for Almanac.

Default behavior stays the MCP server so existing ``python -m memento`` MCP
registrations keep working. Named subcommands provide a local, non-MCP retrieval
surface for skills and agents that can run shell commands but cannot call MCP
tools.
"""

from __future__ import annotations

import argparse
import json
import sys


def _json_dump(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _search(argv: list[str], prog: str) -> int:
    from memento.retrieval_policy import ExplicitSearchRequest, ExplicitSearchRuntime

    parser = argparse.ArgumentParser(prog=f"{prog} search")
    parser.add_argument("query", nargs="+", help="Natural-language question or exact identifier")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--cwd", default="")
    parser.add_argument("--concrete", default="auto", choices=["auto", "true", "false"])
    parser.add_argument("--detail-level", default="summary", choices=["brief", "summary", "full"])
    parser.add_argument("--include-content", action="store_true")
    parser.add_argument("--token-budget", type=int, default=2000)
    args = parser.parse_args(argv)

    runtime = ExplicitSearchRuntime()
    payload = runtime.search(
        ExplicitSearchRequest(
            query=" ".join(args.query),
            limit=args.limit,
            semantic=args.semantic,
            min_score=args.min_score,
            cwd=args.cwd,
            concrete=args.concrete,
            detail_level=args.detail_level,
            include_content=args.include_content,
            token_budget=args.token_budget,
        )
    )
    _json_dump(payload)
    return 0 if payload.get("results") else 1


def _recall(argv: list[str], prog: str) -> int:
    from memento.lifecycle import build_recall

    parser = argparse.ArgumentParser(prog=f"{prog} recall")
    parser.add_argument("prompt", nargs="+", help="Prompt to run through production prompt-recall policy")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--session-id", default="local-cli")
    parser.add_argument("--record", action="store_true", help="Record recall access/dedup state; default is read-only")
    args = parser.parse_args(argv)

    result = build_recall(
        " ".join(args.prompt), cwd=args.cwd, session_id=args.session_id, record=args.record, host_id="cli"
    )
    payload = result.to_dict()
    _json_dump(payload)
    return 0 if payload.get("should_inject") else 1


def _reindex(argv: list[str], prog: str) -> int:
    from memento.config import get_config
    from memento.search_backend import get_backend

    parser = argparse.ArgumentParser(prog=f"{prog} reindex")
    parser.add_argument("--collection", default="")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding/vector update where supported")
    args = parser.parse_args(argv)

    config = get_config()
    collection = args.collection or config.get("qmd_collection", "memento")
    backend = get_backend()
    ok = backend.reindex(collection, embed=not args.no_embed)
    _json_dump({"ok": bool(ok), "backend": type(backend).__name__, "collection": collection})
    return 0 if ok else 1


def main(argv: list[str] | None = None, *, prog: str = "python -m memento") -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else ""
    if command == "search":
        return _search(argv[1:], prog)
    if command == "recall":
        return _recall(argv[1:], prog)
    if command == "reindex":
        return _reindex(argv[1:], prog)
    if command == "tools":
        from memento.mcp_inventory import main as tools_main

        return tools_main(argv[1:])
    if command == "archive":
        from memento.archive import main as archive_main

        return archive_main(argv[1:])
    if command in {"health", "doctor"}:
        from memento.health import main as health_main

        return health_main(argv[1:])
    if command in {"retrieval-report", "retrieval-dashboard"}:
        from memento.retrieval_dashboard import main as dashboard_main

        return dashboard_main(argv[1:])
    if command in {"help", "-h", "--help"}:
        print(
            "Almanac MCP Server\n"
            f"Usage: {prog} [search|recall|reindex|tools|archive|health|retrieval-report] ...\n"
            "Without a subcommand, starts the MCP server."
        )
        return 0

    from memento.mcp_server import main as mcp_main

    mcp_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
