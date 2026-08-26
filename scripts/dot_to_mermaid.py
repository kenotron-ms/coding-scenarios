#!/usr/bin/env python3
"""Render a compiled attractor ``.dot`` pipeline as a GitHub-native Mermaid flowchart.

Deterministic: same ``.dot`` in -> byte-identical Mermaid out. No engine, no LLM,
standard library only. Used by the ``plan-batch`` GitHub Actions workflow to
visualise a compiled goal-plan pipeline inside a GitHub issue comment (GitHub
renders ```mermaid fenced code blocks natively; it does not render Graphviz DOT).

Usage:
    python3 scripts/dot_to_mermaid.py <compiled.dot> [-o out.mmd]
"""

from __future__ import annotations

import argparse
import re
import sys

# graphviz shape -> (open, close) Mermaid node delimiters
_SHAPE: dict[str, tuple[str, str]] = {
    "Mdiamond": ("([", "])"),  # Start
    "Msquare": ("([", "])"),  # Exit
    "diamond": ("{", "}"),
    "parallelogram": ("[/", "/]"),  # tool/gate nodes
    "component": ("[[", "]]"),  # wave launch
    "tripleoctagon": ("{{", "}}"),  # wave collect / fan-in
    "box": ("[", "]"),
}

# The attractor engine routes on this context field; strip it for readable labels.
_COND_PREFIX = "context.tool.last_line"


def _esc(text: str) -> str:
    """Escape characters that break Mermaid node/edge labels."""
    return text.replace('"', "'").replace("<", "&lt;").replace(">", "&gt;")


def _cond_label(attr: str) -> str:
    """Turn an edge attribute block into a short human-readable edge label."""
    m = re.search(r'condition="([^"]*)"', attr)
    if not m:
        return ""
    cond = m.group(1).strip()
    if cond.startswith(_COND_PREFIX):
        rest = cond[len(_COND_PREFIX) :]
        if rest.startswith("!="):
            val = rest[2:].strip().strip("'\"")
            return "else" if val == "" else f"\u2260 {val}"
        if rest.startswith("="):
            return rest[1:].strip().strip("'\"")
    return cond


def dot_to_mermaid(src: str) -> str:
    """Convert Graphviz DOT source into a Mermaid ``flowchart TD`` string."""
    nodes: dict[str, tuple[str, str]] = {}
    order: list[str] = []
    # Node declarations: ``Name [ ...attrs... ];`` (single- or multi-line).
    for m in re.finditer(
        r"^\s*([A-Za-z_]\w*)\s*\[(.*?)\];", src, re.DOTALL | re.MULTILINE
    ):
        nid, attrs = m.group(1), m.group(2)
        if nid in ("graph", "node", "edge"):
            continue
        shape_m = re.search(r"shape=(\w+)", attrs)
        label_m = re.search(r'label="([^"]*)"', attrs)
        shape = shape_m.group(1) if shape_m else "box"
        label = label_m.group(1) if label_m else nid
        if nid not in nodes:
            nodes[nid] = (shape, label)
            order.append(nid)
    # Edges: ``A -> B [ ...attrs... ];``. Anchored so ``<->`` inside a label
    # attribute (e.g. "Plan<->DOT") is never mistaken for an edge.
    edges: list[tuple[str, str, str]] = []
    for m in re.finditer(
        r"^\s*([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*;",
        src,
        re.MULTILINE,
    ):
        edges.append((m.group(1), m.group(2), _cond_label(m.group(3) or "")))

    out = ["flowchart TD"]
    for nid in order:
        shape, label = nodes[nid]
        open_d, close_d = _SHAPE.get(shape, ("[", "]"))
        out.append(f'  {nid}{open_d}"{_esc(label)}"{close_d}')
    for a, b, lbl in edges:
        out.append(f"  {a} -->|{_esc(lbl)}| {b}" if lbl else f"  {a} --> {b}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a compiled attractor .dot as a Mermaid flowchart."
    )
    parser.add_argument("dot", help="path to the compiled .dot file")
    parser.add_argument("-o", "--output", help="write Mermaid here (default: stdout)")
    args = parser.parse_args(argv)

    with open(args.dot, encoding="utf-8") as handle:
        mermaid = dot_to_mermaid(handle.read())

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(mermaid)
    else:
        sys.stdout.write(mermaid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
