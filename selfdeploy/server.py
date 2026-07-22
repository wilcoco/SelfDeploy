"""The CEO's first screen: a local-first, mobile-first `ask` UI.

One input line ("무엇이 궁금하세요?") → the engine wires it (auto-answer cards)
or owns it (delegate cards with owner + due). Below it, today's brief: the top-3
attention items with the '왜 지금' rationale. Zero-typing beyond the one line —
matching the CEO-UX principle from the strategy review.

Local-first is enforced, not promised: the server binds 127.0.0.1 ONLY (never
0.0.0.0), uses stdlib http.server (no external deps), and the page's footer
states the guarantee. Confidential inputs never leave the machine — the answer
to the Samsung-leak / 97%-GenAI-breach landscape (Journey 2026 report, Trend #4).
"""
from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .ask import ANSWERED, ROUTED, UNVERIFIED, ask
from .grounding import Evidence
from .manage import management_surface, rationale, select
from .templates import VerticalTemplate

_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SelfDeploy — 대표의 문</title>
<style>
:root{color-scheme:light dark;--red:#cf222e;--green:#1a7f37;--amber:#9a6700;--mut:#656d76}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,"Apple SD Gothic Neo",sans-serif;
margin:0;padding:1rem;max-width:520px;margin-inline:auto;background:#fafbfc;color:#1f2328}
h1{font-size:1.15rem;margin:.4rem 0 .2rem}.sub{color:var(--mut);font-size:.8rem;margin:0 0 1rem}
form{display:flex;gap:.5rem}input{flex:1;font-size:1rem;padding:.7rem .8rem;border:1.5px solid #d0d7de;
border-radius:10px;background:inherit;color:inherit}button{font-size:1rem;padding:.7rem 1rem;border:0;
border-radius:10px;background:#1f2328;color:#fff;font-weight:700}
.card{border:1px solid #d0d7de;border-left:4px solid var(--mut);border-radius:10px;padding:.7rem .8rem;margin:.6rem 0;background:#fff}
.card.ok{border-left-color:var(--green)}.card.route{border-left-color:var(--red)}.card.unv{border-left-color:var(--amber)}
.k{font-size:.72rem;font-weight:700;letter-spacing:.03em}.ok .k{color:var(--green)}.route .k{color:var(--red)}.unv .k{color:var(--amber)}
.t{font-weight:600;margin:.15rem 0}.d{color:var(--mut);font-size:.82rem}
.meta{display:flex;gap:.5rem;margin-top:.35rem;flex-wrap:wrap}
.chip{font-size:.72rem;border:1px solid #d0d7de;border-radius:999px;padding:.1rem .5rem;color:var(--mut)}
.verdict{font-weight:700;margin:.9rem 0 .3rem}
h2{font-size:.95rem;margin:1.4rem 0 .3rem;border-left:4px solid #1f2328;padding-left:.5rem}
.why{color:var(--mut);font-size:.78rem;margin:.15rem 0 0 .2rem}
.foot{margin-top:1.6rem;border-top:1px solid #d0d7de;padding-top:.6rem;color:var(--mut);font-size:.72rem;line-height:1.5}
@media (prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}.card{background:#161b22;border-color:#30363d}
input{border-color:#30363d}.chip{border-color:#30363d}}
</style></head><body>
<h1>무엇이 궁금하세요?</h1><p class="sub">리스크 방지든 기회 포착이든 — 한 줄이면 됩니다.</p>
<form id="f"><input id="q" placeholder="예: 임원 갑질 리스크 관리되나? / 제품별 마진 알고 싶다"
autocomplete="off"><button>묻기</button></form>
<div id="out"></div>
<h2>오늘의 브리프 — 주의 필요 3건</h2><div id="brief"></div>
<p class="foot"><b>로컬 전용.</b> 이 화면과 엔진은 127.0.0.1에서만 동작하며, 입력한 내용은 이 기계를 떠나지 않습니다.
(대표의 리스크·핵심가치 데이터는 회사 밖으로 나가지 않는 것이 기본값입니다)</p>
<script>
const f=document.getElementById('f'),q=document.getElementById('q'),out=document.getElementById('out');
function card(cls,k,t,d,meta){return `<div class="card ${cls}"><div class="k">${k}</div><div class="t">${t}</div>`+
(d?`<div class="d">${d}</div>`:'')+(meta?`<div class="meta">${meta}</div>`:'')+`</div>`}
f.addEventListener('submit',async e=>{e.preventDefault();if(!q.value.trim())return;
out.innerHTML='<p class="d">배선 중…</p>';
const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({desire:q.value})});const j=await r.json();
let h=`<div class="verdict">→ ${j.verdict}</div>`;
for(const a of j.answered)h+=card('ok','✓ 자동 답',a.label,a.detail,'');
for(const a of j.routed){const chips=`<span class="chip">담당 ${a.owner||'미지정'}</span><span class="chip">기한 ${a.due||''}</span>`+
(a.kind==='unverified'?'<span class="chip">미확인</span>':'');
h+=card(a.kind==='unverified'?'unv':'route',a.kind==='unverified'?'? 미확인 — 확인 요청':'⏳ 담당자에게 물음',a.label,a.detail,chips)}
out.innerHTML=h});
fetch('/api/brief').then(r=>r.json()).then(j=>{
document.getElementById('brief').innerHTML=j.items.map(it=>
card(it.status.startsWith('사각지대')?'route':'unv',`${it.category} · ${it.status}`,it.label,'',
`<span class="chip">담당 ${it.owner||'미지정'}</span><span class="chip">가중치 ${it.weight}</span>`)+
it.why.map(w=>`<div class="why">▸ ${w}</div>`).join('')).join('')});
</script></body></html>"""


def make_handler(vertical: VerticalTemplate, evidence: Evidence, resolver=None, mapper=None):
    at = date.today().isoformat()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj) -> None:
            self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            if self.path == "/":
                self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/brief":
                surface = management_surface(vertical, evidence, resolver=resolver)
                top = select(surface, top=3)
                self._json({"items": [
                    {"label": it.label, "category": it.category, "status": it.status,
                     "owner": it.owner, "weight": round(it.weight, 2), "why": rationale(it)}
                    for it in top
                ]})
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            if self.path != "/api/ask":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0"))
            desire = json.loads(self.rfile.read(length) or b"{}").get("desire", "")
            result = ask(desire, vertical, evidence, at=at, resolver=resolver, mapper=mapper)
            self._json({
                "verdict": result.verdict,
                "escalated": result.escalated,
                "answered": [{"label": r.label, "detail": r.detail}
                             for r in result.resolutions if r.kind == ANSWERED],
                "routed": [{"label": r.label, "detail": r.detail, "owner": r.owner,
                            "due": r.due, "kind": r.kind}
                           for r in result.resolutions if r.kind in (ROUTED, UNVERIFIED)],
            })

        def log_message(self, *_a):  # quiet
            pass

    return Handler


def serve(vertical: VerticalTemplate, evidence: Evidence, port: int = 8787,
          resolver=None, mapper=None) -> ThreadingHTTPServer:
    """Create the local-only server (caller decides serve_forever vs test-drive).

    Binding is hard-coded to 127.0.0.1 — local-first is enforced by construction,
    not configuration. There is deliberately no --host option.
    """
    handler = make_handler(vertical, evidence, resolver=resolver, mapper=mapper)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
