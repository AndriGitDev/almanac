# Almanac demo vault

This is a populated example vault containing **41 fictional notes and project
indexes**. It includes API, web, infrastructure, and data projects, plus five
shared patterns that connect them. The content was written for this demonstration;
it is not captured session history or an actual project's operational guidance.

## Explore it in Obsidian

1. In Obsidian's vault switcher, choose **Open folder as vault**.
2. Select this `examples/demo-vault` directory from your Almanac checkout.
3. Open **Graph view** to explore the full vault, or open a note's **Local graph**
   to see its neighbors.
4. Optionally color graph groups using the demo tags: `#api`, `#web`,
   `#infra`, `#data`, and `#cross-project`.

The README is excluded from the static preview. Obsidian may include it as an
additional unlinked node; filter with `-file:README` to hide it. Obsidian chooses
its own layout and colors, so its view will differ from the static illustration.
Opening the vault does not require installing Almanac or running its hooks.

## Regenerate the README graphic

From the repository root, run:

```bash
python3 scripts/render_demo_graph.py
```

The renderer reads these Markdown files and their `[[wikilinks]]`, checks that all
linked notes exist, and writes `docs/images/vault-graph.svg`. The preview uses a
fixed layout and project colors to keep it readable. It is a graph illustration,
not an Obsidian screenshot.
