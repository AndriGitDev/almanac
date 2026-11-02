#!/usr/bin/env python3
"""Generate shared fragments or check drift; default is read-only."""

import argparse
import inspect
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from almanac.contracts import CONTRACT, integration_fragment  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    targets = {ROOT / "docs/contracts/context-v1.json": json.dumps(CONTRACT, indent=2, sort_keys=True) + "\n"}
    for relative in [
        "skills/almanac/SKILL.md",
        "skills/memento/SKILL.md",
        "skills/generic/almanac/SKILL.md",
        "skills/generic/memento/SKILL.md",
    ]:
        path = ROOT / relative
        current = path.read_text()
        fragment = integration_fragment("memento" if "/memento/" in relative else "almanac")
        marker = r"<!-- almanac-context-contract:start -->.*?<!-- almanac-context-contract:end -->"
        rendered = (
            re.sub(marker, lambda m: fragment, current, flags=re.S)
            if re.search(marker, current, flags=re.S)
            else current.rstrip() + "\n\n" + fragment + "\n"
        )
        targets[path] = rendered
    from almanac.lifecycle import build_session_context
    from almanac.store import normalize_note_contract

    example = CONTRACT["note_example"]
    assert (
        normalize_note_contract(project=example["project"], project_path=example["project_path"])["project"]
        == "almanac"
    )
    assert set(CONTRACT["request_fields"]) <= set(inspect.signature(build_session_context).parameters)
    stale = []
    for path, rendered in targets.items():
        if not path.exists() or path.read_text() != rendered:
            stale.append(str(path.relative_to(ROOT)))
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(rendered)
    if stale and not args.write:
        print("Stale shared contracts: " + ", ".join(stale))
        return 1
    print("Shared context contracts generated." if args.write else "Shared context contracts match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
