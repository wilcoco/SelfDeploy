"""SelfDeploy — an ought-first measurement-grounding engine.

A low-cost stand-in for the Palantir FDE effect, aimed at SMBs. The core move:
take an executive's requirement as the *ought*, decompose it into the substructure
it logically entails, then ground each entailed record against the company's real
evidence. What can't ground is a *red cell* — the hidden layer, surfaced.

Public surface:
    build_graph   requirement -> ought-graph (decompose)
    ground        ought-graph + evidence -> graded graph (deterministic gate)
    Evidence, Signal
    text_report, html_report
    VERTICALS     the Kind-B measurement grammars
"""
from .decompose import build_graph
from .grounding import Evidence, Metrics, Signal, ground, metrics
from .interview import Answer, Question, apply_answers, generate_questions, run_round
from .ir import Contract, ContractGraph, Grade, NodeKind, Provenance
from .llm import ClaudeRequirementMapper
from .report import html_report, text_report
from .templates import VERTICALS, VerticalTemplate

__all__ = [
    "build_graph",
    "ground",
    "Evidence",
    "Signal",
    "Metrics",
    "metrics",
    "Contract",
    "ContractGraph",
    "Grade",
    "NodeKind",
    "Provenance",
    "text_report",
    "html_report",
    "VERTICALS",
    "VerticalTemplate",
    "Answer",
    "Question",
    "generate_questions",
    "apply_answers",
    "run_round",
    "ClaudeRequirementMapper",
]

__version__ = "0.0.1"
