"""The truth-telling gate: red cells -> forced questions -> answers -> re-ground.

This is the moat's first real embodiment. A red cell is not just displayed; it
generates a *specific* question derived from *type non-closure* — not LLM vibes.
"Approve" is replaced by "fill the red cell." Each answer produces a new evidence
signal (or assigns a judgment owner), which is fed back and re-grounded, so the
red-cell density actually drops — the living source-of-truth in miniature.

The question is generated from the contract's kind + why it failed to ground, so
it is deterministic and reproducible. A human cannot rubber-stamp a red cell; the
only way to clear it is to supply the specific missing record or owner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .decompose import build_graph
from .grounding import Evidence, Metrics, Signal, ground, metrics
from .ir import Contract, ContractGraph, Grade, NodeKind, Provenance
from .templates import VerticalTemplate

# Gap types
MISSING_RECORD = "missing_record"
CLAIM_ONLY = "claim_only"
UNOWNED_JUDGMENT = "unowned_judgment"
UNKNOWN_REQUIREMENT = "unknown_requirement"

_PRIORITY = {MISSING_RECORD: 0, UNOWNED_JUDGMENT: 1, UNKNOWN_REQUIREMENT: 1, CLAIM_ONLY: 2}


@dataclass
class Question:
    """A forced question, generated from a contract that failed to close."""

    contract_id: str
    label: str
    gap: str
    prompt: str
    closes_with: str
    grounding_tags: list[str] = field(default_factory=list)

    @property
    def priority(self) -> int:
        return _PRIORITY.get(self.gap, 3)


@dataclass
class Answer:
    """A担당자's response that closes (or partially closes) a red cell.

    Exactly one of: a produced ``signal`` (record/claim now exists) or an
    ``owner`` (a human takes the judgment). ``data=True`` marks the signal as
    data-backed (VERIFIED); otherwise it is a declared plan (UNVERIFIED).
    """

    contract_id: str
    signal_id: Optional[str] = None
    data: bool = False
    owner: Optional[str] = None
    description: str = ""


def _prompt_for(node: Contract, gap: str) -> tuple[str, str]:
    """Return (prompt, closes_with) — a specific question and its closure condition."""
    label = node.label
    if gap == MISSING_RECORD:
        if node.kind == NodeKind.EVENT:
            return (
                f"「{label}」이 실제로 수행된다는 증거가 없다. 이 이벤트가 실제로 일어나나? "
                f"일어난다면 어디에 흔적이 남나? 안 남는다면 무엇을 바꿔야 남나?",
                f"이벤트 발생을 남기는 데이터/기록 신호 (tags: {node.grounding_tags})",
            )
        return (
            f"「{label}」에 해당하는 기록이 없다. (1) 누가 (2) 어느 공정·시점에 "
            f"(3) 무엇을 근거로 이 값을 남기나? 지금 안 남긴다면, 남기게 하려면 무엇을 바꿔야 하나?",
            f"기록 신호 (tags: {node.grounding_tags}) — 데이터면 검증, 계획이면 미검증",
        )
    if gap == CLAIM_ONLY:
        return (
            f"「{label}」이 매뉴얼 문장으로만 존재한다(주장). 실제로 이 값이 적용된 건을 "
            f"데이터로 댈 수 있나? 정의를 체크리스트/코드로 닫을 수 있나? — 데이터로 추궁.",
            f"동일 tags의 kind=data 신호가 붙으면 미검증 → 검증으로 승급",
        )
    if gap == UNOWNED_JUDGMENT:
        return (
            f"「{label}」은 사람 판단이다(억지로 닫지 않음). 누가 이 판단을 내리는가? "
            f"담당을 지정하면 합법적 종착점, 지정 안 하면 빨간 칸으로 남는다.",
            f"판단 담당자(owner) 지정",
        )
    # UNKNOWN_REQUIREMENT
    return (
        f"「{label}」 — 이 요구는 현재 업종 문법에 매핑되지 않는다. 어떤 측정 지표로 "
        f"환원되나? (새 Kind-B 템플릿 채굴 대상)",
        "요구를 알려진 KPI로 환원하거나, 새 템플릿을 저작",
    )


def _classify(node: Contract) -> Optional[str]:
    """Which gap type is this contract, if any. None if it's already fine."""
    if node.kind == NodeKind.UNKNOWN:
        return UNKNOWN_REQUIREMENT
    if node.kind == NodeKind.JUDGMENT and node.grade == Grade.RED:
        return UNOWNED_JUDGMENT
    if node.grade == Grade.RED and node.is_leaf:
        return MISSING_RECORD
    if node.grade == Grade.UNVERIFIED and node.is_leaf:
        return CLAIM_ONLY
    return None


def generate_questions(graph: ContractGraph) -> list[Question]:
    """Walk the grounded graph and emit a forced question per unclosed leaf.

    Only leaves (and unknowns/judgments) generate questions — a red parent is a
    consequence of its children, not its own task. Sorted by priority.
    """
    questions: list[Question] = []
    for node in graph.iter_nodes():
        gap = _classify(node)
        if gap is None:
            continue
        prompt, closes_with = _prompt_for(node, gap)
        questions.append(
            Question(
                contract_id=node.id,
                label=node.label,
                gap=gap,
                prompt=prompt,
                closes_with=closes_with,
                grounding_tags=list(node.grounding_tags),
            )
        )
    questions.sort(key=lambda q: (q.priority, q.contract_id))
    return questions


def apply_answers(base: Evidence, graph: ContractGraph, answers: list[Answer]) -> Evidence:
    """Fold answers into a new Evidence: produced signals + assigned judgment owners."""
    signals = list(base.signals)
    owners = dict(base.judgment_owners)
    for ans in answers:
        node = graph.nodes.get(ans.contract_id)
        tags = list(node.grounding_tags) if node else []
        if ans.owner is not None:
            for tag in tags or [ans.contract_id]:
                owners[tag] = ans.owner
        if ans.signal_id is not None:
            signals.append(
                Signal(
                    id=ans.signal_id,
                    kind="data" if ans.data else "claim",
                    tags=tags,
                    description=ans.description,
                )
            )
    return Evidence(signals=signals, judgment_owners=owners)


@dataclass
class Round:
    """One turn of the interview loop, for reporting the delta."""

    before: Metrics
    after: Metrics
    questions_before: list[Question]
    questions_after: list[Question]

    @property
    def red_closed(self) -> int:
        return self.before.red - self.after.red


def run_round(
    requirement: str,
    vertical: VerticalTemplate,
    evidence: Evidence,
    answers: list[Answer],
    mapper=None,
) -> tuple[ContractGraph, Evidence, Round]:
    """Ground, generate questions, apply answers, re-ground — returns the new state.

    The graph is rebuilt from the (pure) requirement each grounding so no stale
    grade/provenance leaks between rounds.
    """
    g0 = ground(build_graph(requirement, vertical, mapper), evidence)
    q0 = generate_questions(g0)
    new_evidence = apply_answers(evidence, g0, answers)
    g1 = ground(build_graph(requirement, vertical, mapper), new_evidence)
    q1 = generate_questions(g1)
    return g1, new_evidence, Round(metrics(g0), metrics(g1), q0, q1)
