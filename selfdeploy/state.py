"""Management-state persistence: the ④관리 stage gets a memory.

A selection is only management if it is *followed up*. This module persists the
CEO's selected initiatives (a portfolio) and snapshots their status on every
review, so the loop closes: 사각지대 → 진행중 → 관리중 becomes a measurable
trajectory instead of a one-shot report. Stalled items (no movement across
snapshots) surface explicitly — those are where the CEO's follow-up goes next.

Time is an injected ISO date string, so tests stay deterministic and history is
human-readable in the JSON file.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# management-status ranks — movement up this ladder is progress
RANK = {
    "사각지대 (미착수)": 0,
    "진행중 (미확정)": 1,
    "사람이 관리중": 2,
    "관리중 (확보)": 3,
}


@dataclass
class Tracked:
    contract_id: str
    label: str
    category: str
    owner: Optional[str] = None
    history: list[dict] = field(default_factory=list)  # [{"at": "2026-07-08", "status": "..."}]

    @property
    def first_status(self) -> str:
        return self.history[0]["status"] if self.history else "?"

    @property
    def latest_status(self) -> str:
        return self.history[-1]["status"] if self.history else "?"

    @property
    def improved(self) -> bool:
        return RANK.get(self.latest_status, 0) > RANK.get(self.first_status, 0)

    @property
    def stalled_reviews(self) -> int:
        """How many consecutive snapshots the status has NOT moved (0 = moved last time)."""
        if len(self.history) < 2:
            return 0
        n = 0
        latest = self.history[-1]["status"]
        for entry in reversed(self.history[:-1]):
            if entry["status"] == latest:
                n += 1
            else:
                break
        return n


@dataclass
class Portfolio:
    vertical: str
    items: dict[str, Tracked] = field(default_factory=dict)
    reviews: list[str] = field(default_factory=list)  # snapshot dates


def load_portfolio(path: str | Path, passphrase: Optional[str] = None) -> Optional[Portfolio]:
    p = Path(path)
    if not p.exists():
        return None
    raw = p.read_text(encoding="utf-8")

    from .security import decrypt_json, is_encrypted_file

    if is_encrypted_file(p):
        if not passphrase:
            raise ValueError("암호화된 포트폴리오 — passphrase가 필요함")
        data = decrypt_json(raw, passphrase)
    else:
        data = json.loads(raw)
    items = {
        cid: Tracked(cid, d["label"], d["category"], d.get("owner"), d.get("history", []))
        for cid, d in data.get("items", {}).items()
    }
    return Portfolio(vertical=data["vertical"], items=items, reviews=data.get("reviews", []))


def save_portfolio(portfolio: Portfolio, path: str | Path, passphrase: Optional[str] = None) -> None:
    data = {
        "vertical": portfolio.vertical,
        "reviews": portfolio.reviews,
        "items": {cid: {k: v for k, v in asdict(t).items() if k != "contract_id"}
                  for cid, t in portfolio.items.items()},
    }
    if passphrase:
        from .security import encrypt_json

        Path(path).write_text(encrypt_json(data, passphrase), encoding="utf-8")
    else:
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def track(portfolio: Portfolio, selected, at: str) -> int:
    """② 선택 → portfolio: start tracking newly selected items (with their current status)."""
    added = 0
    for it in selected:
        if it.contract_id not in portfolio.items:
            portfolio.items[it.contract_id] = Tracked(
                it.contract_id, it.label, it.category, it.owner,
                history=[{"at": at, "status": it.status}],
            )
            added += 1
    return added


def snapshot(portfolio: Portfolio, current_statuses: dict[str, str], at: str) -> int:
    """④ 관리: record each tracked item's current status; returns how many moved."""
    moved = 0
    for cid, tracked in portfolio.items.items():
        status = current_statuses.get(cid)
        if status is None:
            continue  # not visible this round (e.g. different vertical) — keep last known
        if status != tracked.latest_status:
            moved += 1
        tracked.history.append({"at": at, "status": status})
    portfolio.reviews.append(at)
    return moved


@dataclass
class ProgressSummary:
    total: int
    by_status: dict[str, int]
    improved: int
    stalled: int          # items unmoved for >= 2 consecutive reviews
    graduation_rate: float  # of items that started 사각지대, share that moved up


def progress(portfolio: Portfolio) -> ProgressSummary:
    items = list(portfolio.items.values())
    by_status: dict[str, int] = {}
    for t in items:
        by_status[t.latest_status] = by_status.get(t.latest_status, 0) + 1
    started_blind = [t for t in items if RANK.get(t.first_status, 0) == 0]
    graduated = [t for t in started_blind if RANK.get(t.latest_status, 0) > 0]
    return ProgressSummary(
        total=len(items),
        by_status=by_status,
        improved=sum(1 for t in items if t.improved),
        stalled=sum(1 for t in items if t.stalled_reviews >= 2),
        graduation_rate=(len(graduated) / len(started_blind)) if started_blind else 0.0,
    )
