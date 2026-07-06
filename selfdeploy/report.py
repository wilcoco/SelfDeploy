"""Views projected from the IR: the gap map (text + HTML).

These are *views*, never the source of truth. The IR is authored/grounded; the
report only renders it. The money shot is the red-cell list and the red-cell
density — the metric that decides whether self-serve survives.
"""
from __future__ import annotations

import html
import re

from .grounding import Metrics, metrics
from .ir import ContractGraph, Grade


def _clean(label: str) -> str:
    """Collapse whitespace/newlines so multi-line requirements render on one row."""
    return re.sub(r"\s+", " ", label).strip()

_COLOR = {
    Grade.VERIFIED: "#1a7f37",
    Grade.JUDGMENT: "#0969da",
    Grade.UNVERIFIED: "#9a6700",
    Grade.RED: "#cf222e",
}
_BG = {
    Grade.VERIFIED: "#dafbe1",
    Grade.JUDGMENT: "#ddf4ff",
    Grade.UNVERIFIED: "#fff8c5",
    Grade.RED: "#ffebe9",
}


def _grade(node) -> Grade:
    return node.grade if node.grade is not None else Grade.RED


def text_report(graph: ContractGraph) -> str:
    lines: list[str] = []

    def walk(node_id: str, depth: int) -> None:
        node = graph.get(node_id)
        g = _grade(node)
        indent = "  " * depth
        note = f"  — {node.note}" if node.note else ""
        lines.append(f"{indent}{g.symbol} [{g.value:<10}] {_clean(node.label)}{note}")
        for cid in node.requires:
            walk(cid, depth + 1)

    walk(graph.root_id, 0)

    m = metrics(graph)
    lines.append("")
    lines.append("─" * 60)
    lines.append("간극 요약 / GAP SUMMARY")
    lines.append(
        f"  ✓ verified {m.verified}   ? unverified {m.unverified}   "
        f"✗ red {m.red}   ◐ judgment {m.judgment}   (total {m.total})"
    )
    lines.append(f"  빨간 칸 밀도 (red-cell density): {m.red_density:.0%}")
    # The actionable worklist is the *leaf* red cells — the concrete things to
    # close. Parent KPIs that are red merely inherit it from a child, so they are
    # a consequence, not a task.
    reds = [n for n in graph.iter_nodes() if _grade(n) == Grade.RED and n.is_leaf]
    if reds:
        lines.append("")
        lines.append("  숙제 (빨간 칸 — 여기부터 닫아라):")
        for n in reds:
            lines.append(f"    ✗ {_clean(n.label)}")
    return "\n".join(lines)


def html_report(graph: ContractGraph, title: str = "SelfDeploy — 간극 지도") -> str:
    m = metrics(graph)

    def walk(node_id: str) -> str:
        node = graph.get(node_id)
        g = _grade(node)
        note = f'<span class="note">{html.escape(node.note)}</span>' if node.note else ""
        kids = "".join(walk(cid) for cid in node.requires)
        kids_html = f'<div class="kids">{kids}</div>' if kids else ""
        return (
            f'<div class="cell">'
            f'<div class="row" style="border-left-color:{_COLOR[g]};background:{_BG[g]}">'
            f'<span class="sym" style="color:{_COLOR[g]}">{g.symbol}</span>'
            f'<span class="kind">{html.escape(node.kind.value)}</span>'
            f'<span class="label">{html.escape(_clean(node.label))}</span>{note}'
            f"</div>{kids_html}</div>"
        )

    tree = walk(graph.root_id)
    density_color = _COLOR[Grade.RED] if m.red_density > 0.2 else _COLOR[Grade.VERIFIED]

    return f"""<div class="wrap">
<h1>{html.escape(title)}</h1>
<p class="sub">경영자 요구 → 필연 하부구조 → 실제 기록과의 착지. 빨간 칸 = 은닉층이 표면화된 자리.</p>
<div class="metrics">
  <span class="m" style="color:{_COLOR[Grade.VERIFIED]}">✓ {m.verified} verified</span>
  <span class="m" style="color:{_COLOR[Grade.UNVERIFIED]}">? {m.unverified} unverified</span>
  <span class="m" style="color:{_COLOR[Grade.RED]}">✗ {m.red} red</span>
  <span class="m" style="color:{_COLOR[Grade.JUDGMENT]}">◐ {m.judgment} judgment</span>
  <span class="m density" style="color:{density_color}">빨간 칸 밀도 {m.red_density:.0%}</span>
</div>
<div class="tree">{tree}</div>
</div>
<style>
  :root {{ color-scheme: light dark; }}
  .wrap {{ font-family: ui-sans-serif, system-ui, "Apple SD Gothic Neo", sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.4rem; margin-bottom: .25rem; }}
  .sub {{ color: #656d76; margin-top: 0; }}
  .metrics {{ display: flex; flex-wrap: wrap; gap: .75rem; margin: 1rem 0 1.5rem; font-weight: 600; }}
  .m {{ padding: .25rem .6rem; border: 1px solid currentColor; border-radius: 999px; font-size: .85rem; }}
  .density {{ font-weight: 800; }}
  .cell {{ margin: .3rem 0; }}
  .row {{ display: flex; align-items: baseline; gap: .5rem; padding: .4rem .6rem; border-left: 4px solid; border-radius: 4px; }}
  .sym {{ font-weight: 800; }}
  .kind {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .04em; color: #656d76; min-width: 5.5rem; }}
  .label {{ font-weight: 500; }}
  .note {{ color: #656d76; font-size: .8rem; margin-left: .4rem; }}
  .kids {{ margin-left: 1.4rem; border-left: 1px dashed #d0d7de; padding-left: .5rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #0d1117; color: #e6edf3; }}
    .sub, .kind, .note {{ color: #8b949e; }}
    .kids {{ border-left-color: #30363d; }}
  }}
</style>"""
