"""Exact, contained Markdown references shared by CLI, MCP and composition."""

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from almanac.frontmatter import parse, split_frontmatter
from almanac.revisions import raw_revision, semantic_revision


class SourceError(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def heading_slug(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).casefold()
    text = "".join(c if c.isalnum() or c in "_-" else "-" if c.isspace() else "" for c in text)
    return re.sub("-+", "-", text).strip("-")


def normalize_reference(reference: str) -> tuple[str, str | None]:
    path, sep, section = reference.strip().partition("#")
    if not path:
        raise SourceError("denied_source", "A source path is required")
    if not path.endswith(".md"):
        path = f"notes/{path}.md"
    elif "/" not in path:
        path = f"notes/{path}"
    return path, unquote(section) if sep else None


def section_text(body: str, address: str) -> str:
    """ATX headings only; include children, stop at next peer/ancestor.

    No implicit suffixes: repeated Unicode-normalized slugs are ambiguous.
    Headings in fenced code and HTML comments are ignored. Unclosed fences or
    comments reject section requests rather than guessing a span.
    """
    lines = body.splitlines(keepends=True)
    headings = []
    fence = None
    comment = False
    for index, line in enumerate(lines):
        if fence is not None:
            closing = re.match(r"^ {0,3}(`{3,}|~{3,})[ \t]*$", line.rstrip("\r\n"))
            if closing and closing[1][0] == fence[0] and len(closing[1]) >= len(fence):
                fence = None
            continue
        visible = ""
        rest = line
        while rest:
            if comment:
                _, end, rest = rest.partition("-->")
                if not end:
                    rest = ""
                else:
                    comment = False
            else:
                prefix, start, rest = rest.partition("<!--")
                visible += prefix
                if not start:
                    rest = ""
                else:
                    comment = True
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", visible)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if fence is not None:
            continue
        match = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+[ \t]*)?\s*$", visible)
        if match:
            headings.append((index, len(match[1]), heading_slug(match[2])))
    if fence is not None or comment:
        raise SourceError("malformed_markdown", "Unclosed code fence or HTML comment")
    matches = [h for h in headings if h[2] == address]
    if not matches:
        raise SourceError("missing_section", f"No exact heading address: {address}")
    if len(matches) != 1:
        raise SourceError("ambiguous_section", f"Repeated heading address: {address}")
    start, level, _ = matches[0]
    end = next((i for i, depth, _ in headings if i > start and depth <= level), len(lines))
    return "".join(lines[start:end]).rstrip() + "\n"


def read_reference(vault: Path, reference: str, *, max_bytes: int = 2_000_000) -> dict:
    path, section = normalize_reference(reference)
    root = vault.resolve()
    target = (root / path).resolve()
    if root not in target.parents:
        raise SourceError("denied_source", "Invalid path: traversal or symlink escape outside vault")
    if target.suffix != ".md":
        raise SourceError("denied_source", "Only Markdown sources are supported")
    try:
        with target.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
    except FileNotFoundError as exc:
        raise SourceError("missing_file", "Source does not exist") from exc
    except OSError as exc:
        raise SourceError("unavailable_source", "Source cannot be read") from exc
    if len(raw) > max_bytes:
        raise SourceError("source_too_large", "Source exceeds bounded read limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise SourceError("malformed_source", "Source is not UTF-8") from exc
    fields, body = parse(text)
    fm, _ = split_frontmatter(text)
    rel = str(target.relative_to(root))
    from almanac.evidence import read_evidence
    from almanac.retrieval_policy import citation_evidence

    review_status = "not-specified"
    if fields.get("review_after"):
        try:
            review = datetime.fromisoformat(str(fields["review_after"]).replace("Z", "+00:00"))
            if review.tzinfo is None:
                review = review.replace(tzinfo=timezone.utc)
            review_status = "due" if review <= datetime.now(timezone.utc) else "scheduled"
        except ValueError:
            review_status = "unparseable"
    return {
        "review_status": review_status,
        "evidence": read_evidence(fm),
        "verification": citation_evidence(vault, {"path": rel}),
        "path": rel,
        "reference": rel + (f"#{section}" if section is not None else ""),
        "title": str(fields.get("title") or target.stem),
        "content": section_text(body, section) if section is not None else text,
        "revision": raw_revision(raw),
        "semantic_revision": semantic_revision(text),
        "validity_status": "invalidated" if fields.get("invalidated_by") else "current",
        "metadata": fields,
        "frontmatter": fm,
    }


def attach_source_metadata(vault: Path, results: list[dict], *, cwd: str = "") -> list[dict]:
    """Add bounded evidence/revision status to selected search rows only."""
    for result in results[:50]:
        try:
            source = read_reference(vault, result.get("path", ""))
            result["revision"] = source["revision"]
            result["semantic_revision"] = source["semantic_revision"]
            result["validity_status"] = source["validity_status"]
            result["review_status"] = source["review_status"]
            from almanac.retrieval_policy import citation_evidence

            result["verification"] = citation_evidence(vault, result, cwd=cwd)
        except SourceError:
            pass  # Unavailable remote sources retain their original envelope.
    return results
