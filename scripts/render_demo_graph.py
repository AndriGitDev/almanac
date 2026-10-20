#!/usr/bin/env python3
"""Render the public example vault's wikilinks as a standalone SVG.

Run from any directory: python3 scripts/render_demo_graph.py
Uses only the standard library; never reads the user's configured vault.
"""

from __future__ import annotations

import hashlib
import math
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "examples" / "demo-vault"
OUTPUT = ROOT / "docs" / "images" / "vault-graph.svg"
GROUPS = {
    "api": ("API service", "#75b9ff", 315, 355),
    "web": ("Web application", "#bba1ff", 1110, 355),
    "infra": ("Infrastructure", "#5edac6", 315, 665),
    "data": ("Data pipeline", "#f0c27b", 1110, 665),
    "patterns": ("Shared patterns", "#e4ebf5", 710, 510),
}
PATTERN_LABELS = {
    "bounded-retries": "Budget repeated work",
    "clear-failure-states": "Actionable failures",
    "observable-work": "Traceable work",
    "safe-change": "Recoverable changes",
    "explicit-contracts": "Explicit contracts",
}


def load_graph() -> tuple[dict, set]:
    notes = {}
    for folder in ("notes", "projects"):
        for path in sorted((VAULT / folder).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = re.search(r"^title: (.+)$", text, re.MULTILINE)
            project = re.search(r"^project: (.+)$", text, re.MULTILINE)
            if not title or not project or project[1] not in GROUPS:
                raise ValueError(f"Missing or unknown demo metadata: {path}")
            if path.stem in notes:
                raise ValueError(f"Ambiguous note name: {path.stem}")
            notes[path.stem] = {
                "title": title[1],
                "group": project[1],
                "hub": folder == "projects",
                "links": re.findall(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", text),
            }
    edges = set()
    for slug, note in notes.items():
        for target in note["links"]:
            if target not in notes:
                raise ValueError(f"Broken demo link: {slug} -> {target}")
            if target != slug:
                edges.add(tuple(sorted((slug, target))))
    return notes, edges


def layout(notes: dict) -> dict:
    positions = {}
    for group, (_, _, cx, cy) in GROUPS.items():
        members = sorted(slug for slug, note in notes.items() if note["group"] == group and not note["hub"])
        for i, slug in enumerate(members):
            if group == "patterns":
                positions[slug] = (cx + (24 if i % 2 else -24), 320 + i * 88)
                continue
            jitter = hashlib.sha256(slug.encode()).digest()[0] / 255
            angle = -math.pi / 2 + i * math.tau / len(members) + (jitter - 0.5) * 0.32
            radius = 94 + jitter * 44
            positions[slug] = (cx + math.cos(angle) * radius * 1.2, cy + math.sin(angle) * radius)
        for slug, note in notes.items():
            if note["group"] == group and note["hub"]:
                positions[slug] = (cx, cy)
    return positions


def render() -> None:
    notes, edges = load_graph()
    positions = layout(notes)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900" '
        'role="img" aria-labelledby="title description">',
        '<title id="title">Almanac populated demo vault graph</title>',
        f'<desc id="description">{len(notes)} fictional notes and project indexes connected by {len(edges)} '
        "wikilinks. API, web, infrastructure, and data projects connect through five shared pattern notes. "
        "This is an illustration rendered from the included demo vault, not an Obsidian screenshot.</desc>",
        '<defs><radialGradient id="background"><stop stop-color="#172332"/>'
        '<stop offset="1" stop-color="#0c121c"/></radialGradient></defs>',
        '<rect width="1440" height="900" rx="24" fill="url(#background)"/>',
        '<g font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        '<text x="64" y="61" fill="#7f95b0" font-size="14" letter-spacing="3">ALMANAC / EXAMPLE VAULT</text>',
        '<text x="64" y="112" fill="#f1f5fb" font-size="38" font-weight="650">Your work, connected.</text>',
        f'<text x="1376" y="64" text-anchor="end" fill="#c4d0df" font-size="16">'
        f"{len(notes)} notes · {len(edges)} links · 4 projects</text>",
        '<text x="1376" y="94" text-anchor="end" fill="#8395ab" font-size="14">Fictional demo data</text>',
    ]
    for i, (_, (title, color, _, _)) in enumerate(GROUPS.items()):
        x = 72 + i * 245
        parts.append(f'<circle cx="{x}" cy="155" r="4" fill="{color}"/>')
        parts.append(f'<text x="{x + 15}" y="160" fill="#bac8d9" font-size="15">{escape(title)}</text>')
    parts.append('<path d="M64 185H1376" stroke="#263344"/>')
    for source, target in sorted(edges):
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        same_group = notes[source]["group"] == notes[target]["group"]
        color = GROUPS[notes[source]["group"]][1] if same_group else "#8ea3be"
        parts.append(
            f'<path d="M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}" fill="none" stroke="{color}" '
            f'stroke-opacity="{0.23 if same_group else 0.14}" stroke-width="1.2"/>'
        )
    for slug, note in notes.items():
        x, y = positions[slug]
        group = note["group"]
        color = GROUPS[group][1]
        shared = group == "patterns"
        radius = 9 if note["hub"] else 6 if shared else 4.5
        degree = sum(slug in edge for edge in edges)
        parts.append(f"<g><title>{escape(note['title'])} — {degree} connections</title>")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius * 2.4}" fill="{color}" fill-opacity="0.055"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}"/>')
        if note["hub"]:
            parts.append(
                f'<text x="{x:.1f}" y="{y + 32:.1f}" text-anchor="middle" fill="{color}" font-size="19" '
                f'font-weight="600" >{escape(note["title"])}</text>'
            )
        elif shared:
            parts.append(
                f'<text x="{x + 17:.1f}" y="{y + 5:.1f}" fill="#d6e0ef" font-size="14" >{PATTERN_LABELS[slug]}</text>'
            )
        elif abs(x - GROUPS[group][2]) < 38:
            label = note["title"]
            if len(label) > 37:
                label = label[:34].rstrip() + "…"
            offset = -16 if y < GROUPS[group][3] else 27
            parts.append(
                f'<text x="{x:.1f}" y="{y + offset:.1f}" text-anchor="middle" fill="#a1b1c6" font-size="13" '
                f">{escape(label)}</text>"
            )
        parts.append("</g>")
    parts.extend(
        [
            '<path d="M64 823H1376" stroke="#263344"/>',
            '<text x="64" y="860" fill="#a9b9cd" font-size="15">Every dot is a note. Every line is a [[wikilink]].</text>',
            '<text x="1376" y="860" text-anchor="end" fill="#8395ab" font-size="14">'
            "Rendered from examples/demo-vault · Open the vault in Obsidian to explore</text>",
            "</g></svg>",
        ]
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Rendered {len(notes)} notes and {len(edges)} links to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    render()
