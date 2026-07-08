"""Views projected from the IR: the gap map (text + HTML).

These are *views*, never the source of truth. The IR is authored/grounded; the
report only renders it. The money shot is the red-cell list and the red-cell
density — the metric that decides whether self-serve survives.
"""
from __future__ import annotations

import html
import re

from .grounding import Metrics, metrics
from .ir import CATASTROPHIC, MODERATE, SEVERE, ContractGraph, Grade


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
    return _gap_body(graph, title, metrics(graph))


def _gap_body(graph, title, m):
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


# --------------------------------------------------------------------------- #
# Board-ready one-pager: the CEO / board risk register
# --------------------------------------------------------------------------- #

_SEV_LABEL = [
    (CATASTROPHIC, "치명적", "#cf222e"),
    (SEVERE, "심각", "#bc4c00"),
    (MODERATE, "중대", "#9a6700"),
    (0.0, "경미", "#656d76"),
]


def _sev_label(sev: float) -> tuple[str, str]:
    for threshold, label, color in _SEV_LABEL:
        if sev >= threshold:
            return label, color
    return "경미", "#656d76"


def risk_register_html(vertical_name: str, ceo: list, ops: list, top_n: int) -> str:
    """A one-page, print-to-PDF board report of the CEO blind-spot risk register."""

    def item_row(it) -> str:
        sev_label, sev_color = _sev_label(it.severity)
        sens = "사람만" if it.human_only else "센싱가능"
        who = html.escape(it.owner) if it.owner else "미지정"
        exps = "".join(f'<span class="exp">{html.escape(e)}</span>' for e in (it.exposure or [])) or "—"
        regs = ", ".join(it.regulations or []) or "—"
        risk_pct = int(round(it.risk * 100))
        return (
            "<tr>"
            f'<td class="risk"><span class="bar" style="--w:{risk_pct}%"></span>{it.risk:.2f}</td>'
            f'<td><span class="sev" style="background:{sev_color}">{sev_label}</span></td>'
            f'<td class="grade">{html.escape(it.grade.value)}</td>'
            f'<td class="label">{html.escape(_clean(it.label))}</td>'
            f'<td class="owner">{who}</td>'
            f'<td class="exps">{exps}</td>'
            f'<td class="sens">{sens}</td>'
            f'<td class="reg">{html.escape(regs)}</td>'
            "</tr>"
        )

    def section(rows: list, cls: str) -> str:
        body = "".join(item_row(it) for it in rows) or '<tr><td colspan="8">—</td></tr>'
        return (
            f'<table class="reg-table {cls}"><thead><tr>'
            "<th>위험</th><th>파장</th><th>등급</th><th>통제</th><th>담당</th><th>노출</th><th>센싱</th><th>근거 법규</th>"
            f"</tr></thead><tbody>{body}</tbody></table>"
        )

    total = len(ceo) + len(ops)
    return f"""<div class="board">
<div class="head">
  <h1>대표 리스크 레지스터</h1>
  <div class="meta">{html.escape(vertical_name)} 책임 표면 · 통제 {total}건 · 위험 = 파장 × 미착지도</div>
</div>
<h2 class="ceo-h">대표 escalation — 오늘 밤 못 자는 순서 (상위 {len(ceo)})</h2>
{section(ceo, "ceo")}
<h2 class="ops-h">운영층 worklist (나머지 {len(ops)})</h2>
{section(ops, "ops")}
<p class="foot">이 레지스터는 회사가 <b>표방한 의무에서 필연으로 도출되는 미착지 통제</b>를 파장으로 순위매긴 것이다.
새로운 실패(블랙스완) 예측이 아니라, unknown-unknown을 ranked known-unknown으로 바꾼다.
<b>노출</b>은 통제가 비었을 때의 결과 클래스다 — 법규는 그중 하나일 뿐, 브랜드·여론·정치·노무 노출은 법을 어기지 않고도 대표를 무너뜨린다(스타벅스 판촉 사례형).</p>
</div>
<style>
  :root {{ color-scheme: light dark; }}
  @page {{ size: A4; margin: 14mm; }}
  .board {{ font-family: ui-sans-serif, system-ui, "Apple SD Gothic Neo", sans-serif; max-width: 940px; margin: 1.5rem auto; padding: 0 1rem; color: #1f2328; }}
  .head {{ border-bottom: 3px solid #1f2328; padding-bottom: .5rem; margin-bottom: 1rem; }}
  h1 {{ font-size: 1.5rem; margin: 0; }}
  .meta {{ color: #656d76; font-size: .85rem; margin-top: .25rem; }}
  h2 {{ font-size: 1rem; margin: 1.2rem 0 .4rem; padding-left: .5rem; border-left: 4px solid; }}
  .ceo-h {{ border-color: #cf222e; }}
  .ops-h {{ border-color: #656d76; color: #656d76; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
  th {{ text-align: left; color: #656d76; font-weight: 600; border-bottom: 1px solid #d0d7de; padding: .3rem .4rem; }}
  td {{ padding: .35rem .4rem; border-bottom: 1px solid #eaeef2; vertical-align: top; }}
  .risk {{ position: relative; font-variant-numeric: tabular-nums; font-weight: 700; white-space: nowrap; }}
  .bar {{ display: block; position: absolute; left: 0; bottom: 0; height: 3px; width: var(--w); background: #cf222e; }}
  .sev {{ color: #fff; padding: .05rem .4rem; border-radius: 999px; font-size: .72rem; font-weight: 700; }}
  .grade {{ text-transform: uppercase; font-size: .72rem; letter-spacing: .03em; color: #656d76; }}
  .label {{ font-weight: 500; }}
  .owner {{ white-space: nowrap; }}
  .sens {{ color: #656d76; }}
  .exps {{ line-height: 1.6; }}
  .exp {{ display: inline-block; background: #eef2f6; color: #33404d; border-radius: 999px; padding: .02rem .38rem; font-size: .68rem; margin: 0 .15rem .15rem 0; white-space: nowrap; }}
  .reg {{ color: #444c56; font-size: .78rem; }}
  .ops td {{ opacity: .8; }}
  .foot {{ margin-top: 1.2rem; color: #656d76; font-size: .78rem; line-height: 1.5; border-top: 1px solid #d0d7de; padding-top: .6rem; }}
  @media (prefers-color-scheme: dark) {{
    .board {{ color: #e6edf3; }} .head {{ border-color: #e6edf3; }}
    th {{ border-color: #30363d; }} td {{ border-color: #21262d; }}
    .foot {{ border-color: #30363d; }}
  }}
  @media print {{ .board {{ margin: 0; max-width: none; }} h2 {{ break-after: avoid; }} tr {{ break-inside: avoid; }} }}
</style>"""
